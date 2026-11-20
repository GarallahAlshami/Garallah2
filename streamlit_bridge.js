(() => {
  const send = (type, fields) => parent.postMessage({isStreamlitMessage:true, type, ...fields}, "*");
  let pending, ready;
  const firstRender = new Promise(resolve => { ready = resolve; });
  const nativeFetch = window.fetch.bind(window);
  let queue = firstRender;
  addEventListener("message", e => {
    if (e.source !== parent || e.data.type !== "streamlit:render") return;
    ready();
    const reply = e.data.args.reply;
    if (pending && reply.id === pending.id) {
      const bytes = Uint8Array.from(atob(reply.body), c => c.charCodeAt(0));
      pending.resolve(new Response(bytes.length ? bytes : null, {status:reply.status,headers:reply.headers}));
      pending = undefined;
    }
  });
  window.fetch = (path, options = {}) => {
    if (typeof path !== "string" || !path.startsWith("/api/")) return nativeFetch(path, options);
    const request = queue.then(async () => {
      const req = new Request(new URL(path, location.href), options);
      const bytes = new Uint8Array(await req.arrayBuffer());
      let binary = "";
      for (let i=0;i<bytes.length;i+=8192) binary += String.fromCharCode(...bytes.subarray(i,i+8192));
      const id = crypto.randomUUID();
      return new Promise(resolve => {
        pending = {id,resolve};
        send("streamlit:setComponentValue",{dataType:"json", value:{id,path,method:req.method,headers:Object.fromEntries(req.headers),body:btoa(binary)}});
      });
    });
    queue = request.catch(()=>{});
    return request;
  };
  send("streamlit:componentReady",{apiVersion:1});
  const resize = () => send("streamlit:setFrameHeight",{height:Math.max(680,window.screen.availHeight-100)});
  addEventListener("DOMContentLoaded", resize);
  resize();
})();
