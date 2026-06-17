const i=document.getElementById("ai-curation-root"),d=(i==null?void 0:i.dataset.apiBase)??"/ai/api/",u=d.endsWith("/")?d.slice(0,-1):d;class p{constructor(t){this.baseUrl=t}get(t){return this.request("GET",t)}post(t,e){return this.request("POST",t,e)}async request(t,e,o){try{const n={method:t,headers:{Accept:"application/json","Content-Type":"application/json"},credentials:"same-origin",...o!==void 0?{body:JSON.stringify(o)}:{}},s=await fetch(`${this.baseUrl}${e}`,n),l=await s.json();return s.ok?{ok:!0,data:l}:{ok:!1,error:this.toApiError(l)}}catch(n){return{ok:!1,error:{error:"network_error",detail:n instanceof Error?n.message:"Unknown network error"}}}}toApiError(t){if(typeof t=="object"&&t!==null&&"error"in t){const e=t;return{error:typeof e.error=="string"?e.error:"api_error",detail:typeof e.detail=="string"?e.detail:null}}return{error:"api_error",detail:null}}}class h{constructor(t){this.http=t}getStatus(){return this.http.get("/status")}searchSemantic(t){return this.http.post("/search/semantic",t)}listCollections(){return this.http.get("/collections/")}getCollection(t){return this.http.get(`/collections/${encodeURIComponent(t)}`)}getBookRecommendations(t,e){return this.http.get(`/recommendations/books/${t}?limit=${e}`)}}function b(r){return r.detail??r.error}function g(r){if(!r)return"—";try{return new Date(r).toLocaleString()}catch{return r}}function a(r){const t=document.createElement("span");return t.textContent=r,t.innerHTML}class m{constructor(t,e){this.container=t,this.client=e}mount(){this.container.innerHTML=`
      <div class="container-fluid ai-dashboard">
        <div class="row">
          <div class="col-sm-12">
            <h2 class="ai-dashboard__heading">AI Curated Library</h2>
          </div>
        </div>
        <div id="ai-status-panel" class="row">
          <div class="col-sm-12">
            <div class="ai-spinner">
              <span class="glyphicon glyphicon-refresh ai-spinner__icon"></span>
              Loading status&hellip;
            </div>
          </div>
        </div>
      </div>
    `,this.loadStatus()}async loadStatus(){const t=this.container.querySelector("#ai-status-panel");if(!(t instanceof HTMLElement))return;const e=await this.client.getStatus();if(!e.ok){t.innerHTML=`
        <div class="col-sm-12">
          <div class="alert alert-danger">
            <strong>Could not reach sidecar:</strong> ${a(b(e.error))}
          </div>
        </div>`;return}t.innerHTML=this.renderStatus(e.data)}renderStatus(t){const e=t.library.metadataDbReadable?'<span class="label label-success">Readable</span>':'<span class="label label-danger">Not found</span>',o=t.library.bookCount>0?Math.round(t.library.indexedBookCount/t.library.bookCount*100):0,n=t.lastIngestionRun,s=n?`<tr><td>Last scan</td><td>${a(g(n.startedAt))}</td></tr>
         <tr><td>Scan status</td><td><code>${a(n.status)}</code></td></tr>
         <tr><td>Books scanned</td><td>${n.scannedBooks.toLocaleString()}</td></tr>
         <tr><td>Chunks embedded</td><td>${n.embeddedChunks.toLocaleString()}</td></tr>
         <tr><td>Errors</td><td>${n.errorCount}</td></tr>`:'<tr><td colspan="2">No ingestion runs yet.</td></tr>';return`
      <div class="col-sm-6">
        <div class="panel panel-default">
          <div class="panel-heading"><h3 class="panel-title">Library Index</h3></div>
          <table class="table table-condensed">
            <tbody>
              <tr><td>Calibre metadata.db</td><td>${e}</td></tr>
              <tr><td>Total books</td><td>${t.library.bookCount.toLocaleString()}</td></tr>
              <tr>
                <td>Indexed</td>
                <td>
                  ${t.library.indexedBookCount.toLocaleString()} / ${t.library.bookCount.toLocaleString()}
                  <div class="progress" style="margin:4px 0 0;height:8px">
                    <div class="progress-bar" style="width:${o}%"></div>
                  </div>
                </td>
              </tr>
              <tr><td>Pending</td><td>${t.library.pendingBookCount.toLocaleString()}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="col-sm-6">
        <div class="panel panel-default">
          <div class="panel-heading"><h3 class="panel-title">Embedding &amp; Ingestion</h3></div>
          <table class="table table-condensed">
            <tbody>
              <tr><td>Provider</td><td><code>${a(t.embedding.provider)}</code></td></tr>
              <tr><td>Model</td><td><code>${a(t.embedding.model)}</code></td></tr>
              ${s}
            </tbody>
          </table>
        </div>
      </div>`}}const v=new p(u),y=new h(v),c=document.getElementById("ai-curation-root");c instanceof HTMLElement&&new m(c,y).mount();
