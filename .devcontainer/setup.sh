set -eu
umask 077
mkdir -p database reports/shap_plots models data
test -s ~/.ews-admin || python -c 'import secrets; print(secrets.token_urlsafe(24))' > ~/.ews-admin
export EWS_ADMIN_PASSWORD="$(cat ~/.ews-admin)"
python -m pip install -r requirements.txt
python run.py --setup-only
