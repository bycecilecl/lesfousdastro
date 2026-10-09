const fs=require('fs'),vm=require('vm'),assert=require('assert');
function element(){return {value:'',listeners:{},children:[],addEventListener(name,fn){this.listeners[name]=fn;},replaceChildren(...items){this.children=items;}};}
const ids=['lieu_naissance','suggestions-lieux','lat','lon','tzid','rs_lieu_choice','rs-lieu-suggestions','rs_lat_choice','rs_lon_choice','rs_tzid_choice'];
const elements=Object.fromEntries(ids.map(id=>[id,element()]));
let timers=[],requests=[];
const context={document:{getElementById:id=>elements[id],createElement:()=>element()},console,rsLieuResults:[],setTimeout(fn){timers.push(fn);return fn;},clearTimeout(fn){timers=timers.filter(t=>t!==fn);},fetch(url){return new Promise(resolve=>requests.push({url,resolve}));}};
vm.createContext(context);const template=fs.readFileSync(require('path').join(__dirname,'../templates/astro_form.html'),'utf8');
const start=template.indexOf('    // Géocodage :');
const end=template.indexOf('    createStars();',start);
assert(start>=0 && end>start);
vm.runInContext(template.slice(start,end),context);
const result={label:'Paris, France',lat:48.85,lon:2.35,tzid:'Europe/Paris'};
async function tick(){await new Promise(resolve=>setImmediate(resolve));}
(async()=>{
 for(const [input,list,lat,lon,tz] of [['lieu_naissance','suggestions-lieux','lat','lon','tzid'],['rs_lieu_choice','rs-lieu-suggestions','rs_lat_choice','rs_lon_choice','rs_tzid_choice']]){
  elements[input].value='Par';elements[input].listeners.input();timers.shift()();requests.shift().resolve({ok:true,json:async()=>({results:[result]})});await tick();
  assert.equal(elements[list].children.length,1);
  elements[input].value=result.label;elements[input].listeners.input();assert.equal(elements[lat].value,48.85);assert.equal(elements[lon].value,2.35);assert.equal(elements[tz].value,'Europe/Paris');assert.equal(timers.length,0);
  elements[input].value='Lyon';elements[input].listeners.input();assert.equal(elements[lat].value,'');timers.shift()();const old=requests.shift();
  elements[input].value='Lille';elements[input].listeners.input();timers.shift()();const newer=requests.shift();
  newer.resolve({ok:true,json:async()=>({results:[{...result,label:'Lille, France',lat:50.6}]})});await tick();
  old.resolve({ok:true,json:async()=>({results:[result]})});await tick();assert.equal(elements[list].children[0].value,'Lille, France');
 }
 console.log('OK : sélection mobile immédiatement enregistrée, coordonnées effacées à la modification, réponses obsolètes ignorées dans les deux champs.');
})();
