const test = require('node:test');
const assert = require('node:assert/strict');
const bridge = require('../assets/js/continuity-record-relationship-visuals.js');
const contract = require('../assets/js/continuity-record-relationships.js');
const inspector = require('../assets/js/continuity-relationship-inspector.js');

const model = { width:1200, height:475, nodes:[
  {key:'history:11',kind:'history',x:108,y:122,record:{id:11,title:'Approve <script> update',project_id:'p1'}},
  {key:'schedule:22',kind:'schedule',x:820,y:348,record:{id:22,title:'Implement & test',project_id:'p1'}}
] };
const relation = () => ({id:'rel1',userId:'u1',projectId:'p1',kind:'dependency',state:'documented',
  from:{type:'event',id:11},to:{type:'action',id:22},
  statement:'Decision enabled implementation <img src=x onerror=alert(1)>',
  proof:{mode:'user-confirmed',confirmedBy:'u1',confirmedAt:'2026-11-01T12:00:00Z'}});
const project = rows => ({id:'p1',user_id:'u1',
  canvasRelationshipBundle:{projectId:'p1',userId:'u1',relationships:rows}});
const links = () => bridge.plan(project([relation()]),model,contract).links;

class FakeNode {
  constructor(tag) {this.tag=tag;this.children=[];this.attrs={};this.handlers={};this.textContent='';}
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.children=[...items];}
  setAttribute(k,v){this.attrs[k]=v;}
  addEventListener(name,fn){this.handlers[name]=fn;}
}
const doc={createElement:tag=>new FakeNode(tag)};

test('a validated link exposes real endpoint titles and accepted proof mode',()=>{
  const info=inspector.view(links()[0],model);
  assert.equal(info.fromTitle,'Approve <script> update');
  assert.equal(info.toTitle,'Implement & test');
  assert.equal(info.proofMode,'user-confirmed');
});
test('no links means no controls and no Inspector changes',()=>{
  const nav=new FakeNode('nav'), panel=new FakeNode('aside');
  assert.deepEqual(inspector.attach(doc,nav,[],model,()=>{}),[]);
  assert.equal(nav.children.length,0);
  assert.equal(inspector.inspect(doc,panel,null,model),false);
  assert.equal(panel.children.length,0);
});
test('missing, forged, and invalid endpoints fail closed',()=>{
  const valid=links()[0];
  for(const change of [{fromKey:'history:999'}, {toKey:'history:11'},
      {kind:'similarity'}, {proofMode:'unverified'}, {statement:''}]){
    assert.equal(inspector.view({...valid,...change},model),null);
  }
});
test('Inspector content is text, never parsed HTML',()=>{
  const panel=new FakeNode('aside');
  assert.equal(inspector.inspect(doc,panel,links()[0],model),true);
  assert.equal(panel.children[2].textContent,'From: Approve <script> update');
  assert.match(panel.children[4].textContent,/<img src=x/);
  assert.equal(panel.children.every(n=>n.children.length===0),true);
});
test('Navigator relationship button invokes selection and uses pressed state',()=>{
  const nav=new FakeNode('nav'), selected=[];
  const buttons=inspector.attach(doc,nav,links(),model,(link,info)=>selected.push([link.id,info.kind]));
  assert.equal(buttons.length,1);
  assert.equal(nav.children[0].textContent,'DOCUMENTED CONNECTIONS');
  assert.equal(buttons[0].attrs['aria-pressed'],'false');
  buttons[0].handlers.click();
  assert.deepEqual(selected,[['rel1','dependency']]);
  assert.equal(buttons[0].attrs['aria-pressed'],'true');
});
test('unconfirmed and cross-project relations never create Inspector controls',()=>{
  const bad = {...relation(), proof:null};
  const foreign = {...relation(), projectId:'p2'};
  for(const row of [bad,foreign]){
    const nav=new FakeNode('nav');
    const result=bridge.plan(project([row]),model,contract);
    assert.equal(result.links.length,0);
    assert.equal(inspector.attach(doc,nav,result.links,model,()=>{}).length,0);
  }
});
test('views do not mutate model or supplied validated links',()=>{
  const l=links(); const before=JSON.stringify({l,model});
  const nav=new FakeNode('nav');
  inspector.view(l[0],model);
  inspector.attach(doc,nav,l,model,()=>{});
  assert.equal(JSON.stringify({l,model}),before);
});
test('source-evidence proof renders a distinct support caption',()=>{
  const original=links()[0];
  const panel=new FakeNode('aside');
  assert.equal(inspector.inspect(doc,panel,{...original,proofMode:'accepted-source'},model),true);
  assert.equal(panel.children[5].textContent,'Support: Accepted source evidence');
});
