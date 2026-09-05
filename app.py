import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix, roc_curve
from xgboost import XGBClassifier
import shap

st.set_page_config(page_title='نظام الإنذار المبكر للتسرب الدراسي', page_icon='🎓', layout='wide')
FEATURES=['gpa_sem1','attendance_rate','academic_warnings','lms_activity','failed_courses','credits_completed','age','commute_minutes','financial_stress']
LABELS={'gpa_sem1':'المعدل','attendance_rate':'الحضور','academic_warnings':'الإنذارات الأكاديمية','lms_activity':'نشاط منصة التعلم','failed_courses':'المقررات المتعثرة','credits_completed':'الساعات المجتازة','age':'العمر','commute_minutes':'زمن التنقل','financial_stress':'الضغط المالي'}

@st.cache_data
def make_data(n=4000, seed=42):
    rng=np.random.default_rng(seed)
    d=pd.DataFrame({'student_id':[f'ST-{i:04d}' for i in range(1,n+1)],'gpa_sem1':np.clip(rng.normal(2.65,.65,n),.5,4),'attendance_rate':np.clip(rng.normal(78,14,n),25,100),'academic_warnings':np.clip(rng.poisson(.8,n),0,5),'lms_activity':np.clip(rng.normal(62,22,n),0,100),'failed_courses':np.clip(rng.poisson(.7,n),0,6),'credits_completed':np.clip(rng.normal(27,9,n),6,48),'age':np.clip(np.round(rng.normal(21.5,2.2,n)),18,35).astype(int),'commute_minutes':np.clip(np.round(rng.normal(38,22,n)),0,150).astype(int),'financial_stress':rng.integers(0,4,n)})
    logit=1.8-1.65*(d.gpa_sem1-2.5)-.035*(d.attendance_rate-70)-.018*(d.lms_activity-50)+.48*d.academic_warnings+.42*d.failed_courses-.045*(d.credits_completed-24)+.25*d.financial_stress+.004*d.commute_minutes
    p=1/(1+np.exp(-logit)); d['dropout_risk']=rng.binomial(1,p)
    return d

@st.cache_resource
def train_models():
    d=make_data(); X=d[FEATURES]; y=d.dropout_risk
    Xt,Xv,yt,yv=train_test_split(X,y,test_size=.2,random_state=42,stratify=y)
    prep=ColumnTransformer([('num',Pipeline([('imputer',SimpleImputer(strategy='median')),('scaler',StandardScaler())]),FEATURES)])
    lr=Pipeline([('prep',prep),('model',LogisticRegression(max_iter=2000,class_weight='balanced'))]); lr.fit(Xt,yt)
    xgb=Pipeline([('prep',prep),('model',XGBClassifier(n_estimators=250,max_depth=4,learning_rate=.05,subsample=.85,colsample_bytree=.85,eval_metric='logloss',random_state=42))]); xgb.fit(Xt,yt)
    def ev(m):
        pred=m.predict(Xv); prob=m.predict_proba(Xv)[:,1]; fpr,tpr,_=roc_curve(yv,prob)
        return {'Accuracy':accuracy_score(yv,pred),'Precision':precision_score(yv,pred,zero_division=0),'Recall':recall_score(yv,pred,zero_division=0),'F1':f1_score(yv,pred,zero_division=0),'AUC-ROC':roc_auc_score(yv,prob),'CM':confusion_matrix(yv,pred),'fpr':fpr,'tpr':tpr}
    return d,lr,xgb,{'Logistic Regression':ev(lr),'XGBoost':ev(xgb)}

df,lr,xgb,metrics=train_models()

def scored(data):
    out=data.copy(); p=xgb.predict_proba(data[FEATURES])[:,1]; out['risk_probability']=p; out['risk_percent']=np.round(p*100,1); out['risk_level']=pd.cut(p,[0,.4,.7,1],labels=['منخفض','متوسط','مرتفع'],include_lowest=True); return out

st.sidebar.title('🎓 نظام الإنذار المبكر'); page=st.sidebar.radio('القائمة',['لوحة التحكم','تقييم طالب','تحليل الدفعة','تفسير SHAP','تقييم النماذج','حول النظام']); st.sidebar.info('البيانات صناعية Demo. لا تستخدم النتائج لاتخاذ قرارات فعلية بحق الطلاب.')

if page=='لوحة التحكم':
    st.title('لوحة التحكم الرئيسية'); s=scored(df); hi=int((s.risk_probability>=.7).sum()); me=int(((s.risk_probability>=.4)&(s.risk_probability<.7)).sum()); lo=len(s)-hi-me
    a,b,c,d=st.columns(4); a.metric('إجمالي الطلاب',f'{len(s):,}'); b.metric('خطر مرتفع',hi); c.metric('خطر متوسط',me); d.metric('متوسط الخطر',f'{s.risk_probability.mean()*100:.1f}%')
    l,r=st.columns(2)
    with l: st.subheader('توزيع المخاطر'); st.bar_chart(pd.Series({'منخفض':lo,'متوسط':me,'مرتفع':hi}))
    with r: st.subheader('أعلى الحالات'); st.dataframe(s.sort_values('risk_probability',ascending=False)[['student_id','risk_percent','risk_level']].head(15),use_container_width=True,hide_index=True)
    st.subheader('سير عمل النظام'); st.markdown('**بيانات → معالجة → Logistic Regression + XGBoost → تقييم → SHAP → تدخل وقائي.**')

elif page=='تقييم طالب':
    st.title('🔎 تقييم طالب بشكل فردي'); sid=st.selectbox('رقم الطالب',df.student_id.tolist()); row=df[df.student_id==sid].iloc[0]; X=pd.DataFrame([{f:row[f] for f in FEATURES}]); p=float(xgb.predict_proba(X)[0,1]); level='مرتفع' if p>=.7 else ('متوسط' if p>=.4 else 'منخفض')
    a,b,c=st.columns(3); a.metric('الطالب',sid); b.metric('احتمالية التسرب',f'{p*100:.1f}%'); c.metric('مستوى الخطر',level)
    if p>=.7: st.error('توصية: تدخل أكاديمي عاجل ومراجعة أسباب التعثر.')
    elif p>=.4: st.warning('توصية: متابعة قريبة وخطة دعم وقائية.')
    else: st.success('توصية: متابعة دورية؛ لا توجد إشارة خطر مرتفعة حاليًا.')
    st.dataframe(pd.DataFrame({'المؤشر':[LABELS[f] for f in FEATURES],'القيمة':[row[f] for f in FEATURES]}),use_container_width=True,hide_index=True)

elif page=='تحليل الدفعة':
    st.title('📊 تحليل دفعة كاملة'); up=st.file_uploader('ارفع CSV بنفس أسماء الحقول',type='csv'); work=pd.read_csv(up) if up else df.copy(); missing=[f for f in FEATURES if f not in work.columns]
    if missing: st.error('حقول ناقصة: '+', '.join(missing))
    else:
        s=scored(work); selected=st.multiselect('مستويات الخطر',['منخفض','متوسط','مرتفع'],default=['منخفض','متوسط','مرتفع']); view=s[s.risk_level.astype(str).isin(selected)].sort_values('risk_probability',ascending=False); st.dataframe(view,use_container_width=True,hide_index=True); st.download_button('⬇️ تصدير CSV',view.to_csv(index=False).encode('utf-8-sig'),'early_warning_results.csv','text/csv')

elif page=='تفسير SHAP':
    st.title('🧠 تفسير التنبؤ باستخدام SHAP'); sid=st.selectbox('رقم الطالب',df.student_id.tolist(),key='shap'); row=df[df.student_id==sid].iloc[0]; X=pd.DataFrame([{f:row[f] for f in FEATURES}]); p=float(xgb.predict_proba(X)[0,1]); st.metric('احتمالية التسرب',f'{p*100:.1f}%')
    prep=xgb.named_steps['prep']; estimator=xgb.named_steps['model']; transformed=prep.transform(X); values=shap.TreeExplainer(estimator).shap_values(transformed); values=values[1] if isinstance(values,list) else values; vals=np.asarray(values)[0]; imp=pd.DataFrame({'المتغير':[LABELS[f] for f in FEATURES],'SHAP':vals}).sort_values('SHAP'); st.caption('الموجب يرفع الخطر، والسالب يخفضه.'); st.bar_chart(imp.set_index('المتغير').SHAP); st.dataframe(imp.reindex(imp.SHAP.abs().sort_values(ascending=False).index).head(5),use_container_width=True,hide_index=True)

elif page=='تقييم النماذج':
    st.title('🧪 تقييم ومقارنة النماذج'); table=pd.DataFrame([{ 'النموذج':n, **{k:v for k,v in m.items() if k in ['Accuracy','Precision','Recall','F1','AUC-ROC']}} for n,m in metrics.items()]).set_index('النموذج'); st.dataframe(table.style.format('{:.4f}'),use_container_width=True); st.bar_chart(table); fig,ax=plt.subplots(figsize=(8,5));
    for n,m in metrics.items(): ax.plot(m['fpr'],m['tpr'],label=f"{n} AUC={m['AUC-ROC']:.3f}")
    ax.plot([0,1],[0,1],'--',label='Random'); ax.set_xlabel('False Positive Rate'); ax.set_ylabel('True Positive Rate'); ax.set_title('ROC Curve'); ax.legend(); ax.grid(alpha=.2); st.pyplot(fig)
    st.info('النتائج الحالية ناتجة عن Dataset صناعية للمحاكاة، وليست بيانات جامعة فعلية.')

else:
    st.title('حول النظام'); st.markdown('### نظام إنذار مبكر ذكي للحد من تسرب الطالب\n\nالنظام يتنبأ باحتمال الخطر، يقارن نموذجين، ويستخدم SHAP لتفسير العوامل المؤثرة. البيانات الحالية صناعية لأغراض العرض الأكاديمي. عند توفر Dataset مؤسسية معتمدة يمكن استبدال مصدر البيانات وإعادة التدريب.')
