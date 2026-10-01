const el=id=>document.getElementById('cal-'+id),checked=id=>!!el(id)?.checked;
const personalInstructions=el('instructions')?.textContent||'';
const escapeCal=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const localKey=x=>new Intl.DateTimeFormat('en-CA',{timeZone:calData.fuseau,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(x));
const fmt=x=>x?new Intl.DateTimeFormat('fr-FR',{timeZone:calData.fuseau,day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}).format(new Date(x)):'hors de la fenêtre de recherche';
const bounds=p=>[p.start?+new Date(p.start):-Infinity,p.end?+new Date(p.end):Infinity];
function groupContacts(periods){
 const groups=[];const axes={'Ascendant':'Asc–Dsc','Descendant':'Asc–Dsc','MC':'MC–FC','Milieu du Ciel':'MC–FC','FC':'MC–FC','Fond du Ciel':'MC–FC'};
 const families={'sextile':'60/120','trigone':'60/120','conjonction':'0/180','opposition':'0/180','carré':'90'};
 for(const p of periods){const axis=axes[p.point],family=families[p.aspect];const [a,b]=bounds(p);
  let g=axis&&family?groups.find(g=>g.planete===p.planete&&g.axis===axis&&g.family===family&&!g.contacts.some(c=>c.point===p.point)&&Math.max(bounds(g)[0],a)<Math.min(bounds(g)[1],b)):null;
  if(!g){g={axis,family,planete:p.planete,lente:p.lente,maitre:p.maitre_ascendant,start:p.start,end:p.end,contacts:[],label:axis?p.planete+' → axe '+axis:p.planete+' '+p.aspect+' '+p.point};groups.push(g)}
  else {if(a<bounds(g)[0])g.start=p.start;if(b>bounds(g)[1])g.end=p.end}
  g.contacts.push(p);
 }
 // Fusion visuelle des périodes de Jupiter qui se chevauchent uniquement.
 const merged=[];
 for(const g of groups.sort((a,b)=>bounds(a)[0]-bounds(b)[0])){
  const previous=g.planete==='Jupiter'?merged.findLast(x=>x.planete==='Jupiter'):null;
  if(previous&&bounds(g)[0]<=bounds(previous)[1]){
   previous.contacts.push(...g.contacts);
   if(bounds(g)[1]>bounds(previous)[1])previous.end=g.end;
   previous.maitre=previous.maitre||g.maitre;
   previous.jupiterBundle=true;
   previous.label='Jupiter · '+previous.contacts.length+' contacts';
  }else merged.push(g);
 }
 return merged.sort((a,b)=>bounds(a)[0]-bounds(b)[0]);
}
const groups=groupContacts([...(calData.periods_1||[]).filter(p=>!p.lente),...(calData.periods||[]).filter(p=>p.lente)]);
const enabled=g=>{
 const view=el('view')?.value||'personal';
 if(!checked('mars'))return false;
 if(g.planete==='Lune')return view==='lunar';
 if(view==='lunar'||!el('planet-'+g.planete)?.checked)return false;
 if(view==='rs')return g.contacts.some(p=>!!p.lien_rs);
 if(view==='fast')return !g.lente;
 if(g.planete==='Mercure')return false;
 return g.lente||g.contacts.some(p=>!!p.lien_natal||p.maitre_ascendant);
};
function viewReasons(g){
 const view=el('view')?.value||'personal';
 if(view==='fast')return ['Vue complète des rapides : ce contact est affiché sans filtre de résonance natale ou annuelle.'];
 if(view==='lunar')return ['Exploration lunaire : contact ponctuel à 1°, sans classement parmi les transits personnels essentiels.'];
 return [...new Set(g.contacts.flatMap(p=>(p.raisons||[]).filter(r=>view==='rs'
   ? r.startsWith('Duo présent dans la RS')||r.startsWith('Fenêtre affichée découpée')
   : r.startsWith('Climat de fond')||r.startsWith('Duo présent au natal')||r.startsWith('Contact au maître'))))];
}
const eventVisible=e=>e.kind==='station'?checked('mars')&&checked('planet-'+e.planete):e.kind==='solar'?checked('mars'):checked('moon');
const visibleDay=(g,d)=>overlaps(g,d);
const overlaps=(g,d)=>bounds(g)[0]<+new Date(d.fin)&&bounds(g)[1]>+new Date(d.debut);
let selected=calData.jours.find(d=>d.date===localKey(new Date()))||calData.jours[0];
let selectedGroup=null;
let focusedSlow=null;
let selectedClimate=null;
const skyEvents=calData.ciel_collectif?.evenements||[];
const skyPeriods=calData.ciel_collectif?.periodes_aspects||[];
const skyRetro=calData.ciel_collectif?.retrogradations||[];
const skyStations=calData.ciel_collectif?.periodes_stationnaires||[];
const personalMovers=new Set(['Mercure','Vénus','Mars']);
const skyBackgroundPlanets=new Set(['Uranus','Neptune','Pluton']);
const skyMoverKind=p=>personalMovers.has(p.planete)?'personal':'slow';
const skyClimate=p=>p.planetes?.every(planete=>skyBackgroundPlanets.has(planete));
const skyClass=e=>e.station?'sky-station':e.entree_signe?'sky-entree':e.nature==='tension'?'sky-tension':e.nature==='fluide'?'sky-fluide':'sky-neutral';
const skyEventsOn=date=>skyEvents.filter(e=>e.date===date&&(e.station||e.entree_signe));
const skyPeriodsOn=day=>skyPeriods.filter(p=>overlaps(p,day));
const skyRetroOn=date=>skyRetro.filter(p=>p.debut<=date&&date<=p.fin);
const skyStationOn=date=>skyStations.filter(p=>p.debut<=date&&date<=p.fin);
const skyEventLabel=e=>e.station?(e.direction==='direct'?`${e.planete} reprend sa marche directe`:`${e.planete} devient rétrograde`):e.titre;
const skyDate=date=>new Intl.DateTimeFormat('fr-FR',{day:'numeric',month:'short'}).format(new Date(date+'T12:00:00Z'));
let selectedSkyPeriod=null;
function exactDays(g){return [...new Set(g.contacts.flatMap(c=>c.exacts||[]).map(localKey))]}
function movementDetails(p){
 const m=p.mouvements?.[selected.date];let h='';
 if(m){const phase=m.phase==='exact'?'★ Passage exact ce jour':m.phase==='approche'?"S’approche de l’exact":"S’éloigne de l’exact";h+=`<p class="cal-motion"><strong>${phase}</strong><br>${m.retrograde?'Mouvement rétrograde':'Mouvement direct'} · orbe ${m.orbe.toFixed(2)}°<br><small>Repère au ${fmt(m.date)}${m.exacts.length?' · exact à '+m.exacts.map(fmt).join(', '):''}</small></p>`;}
 const passages=p.passages||[];
 if(passages.length>1)h+='<p class="muted">Passages retrouvés (recherche : 120 jours avant et après le mois) :<br>'+passages.map(x=>`${fmt(x.date)} · ${x.retrograde?'rétrograde':'direct'}`).join('<br>')+'</p>';
 return h;
}
function stationDetails(e){
 if(e.kind!=='station')return '';
 return `<p>${e.degre.toFixed(2)}° ${escapeCal(e.signe)}</p>`+(e.contacts.length?e.contacts.map(c=>`<p class="${c.maitre?'cal-ruler-badge':'muted'}">${escapeCal(c.aspect)} ${escapeCal(c.point)} natal · orbe ${c.orbe.toFixed(2)}°${c.maitre?' · maître d’Ascendant':''}</p>`).join(''):'<p class="muted">Repère collectif : aucun contact natal retenu à cette station.</p>');
}
function shortReading(p){
 const r=p.lecture_courte;if(!r)return '';
 return `<div class="cal-reading"><p>${escapeCal(r.texte)}</p>${r.personnalisation?`<p>${escapeCal(r.personnalisation)}</p>`:''}${r.domaines.length?`<p><strong>Domaines concernés</strong>${r.domaines.map(escapeCal).join(' · ')}</p>`:''}${r.faits.length?`<details><summary>Maisons et maîtrises natales</summary><ul>${r.faits.map(f=>`<li>${escapeCal(f)}</li>`).join('')}</ul></details>`:''}</div>`;
}
function contactDetails(g){
 if(g.jupiterBundle){
  return '<h3>Jupiter — contacts de la période</h3><p class="muted">Un seul ruban, des contacts dont les dates restent distinctes.</p>'+g.contacts.map(p=>contactDetails({planete:p.planete,lente:p.lente,maitre:p.maitre_ascendant,label:p.planete+' '+p.aspect+' '+p.point,contacts:[p]})).join('');
 }

 const levels={prioritaire:'Climat de fond actif',declencheur:'Déclencheur personnel',climat:'Climat ponctuel'};
 const rank={prioritaire:0,declencheur:1,climat:2};const level=g.contacts.map(p=>p.niveau||'climat').sort((a,b)=>rank[a]-rank[b])[0];
 let h=`<section class="cal-contact"><details class="cal-contact-details"><summary>${escapeCal(g.label)}</summary>${g.planete==='Lune'?'<p class="muted">Contact de quelques heures, affiché sur le jour concerné. Seuls les horaires ci-dessous correspondent à l’orbe de 1°.</p>':''}<p class="muted">${el('view')?.value==='rs'?'Écho à la révolution solaire':el('view')?.value==='lunar'?'Exploration lunaire':el('view')?.value==='fast'?'Contact rapide':levels[level]}</p>${g.maitre?'<p class="cal-ruler-badge">Contact au maître de ton Ascendant natal</p>':''}`;
 h+=shortReading(g.contacts[0]);
 const reasons=viewReasons(g);h+='<ul>'+reasons.map(r=>`<li>${escapeCal(r)}</li>`).join('')+'</ul>';
 h+='<div class="event">'+movementDetails(g.contacts[0])+g.contacts.map(p=>`<strong>${escapeCal(p.planete)} ${escapeCal(p.aspect)} ${escapeCal(p.point)} natal</strong>`).join('');
 const windows=[...new Set(g.contacts.map(p=>`${fmt(p.start)} → ${fmt(p.end)}`))];const broad=[...new Set(g.contacts.map(p=>`${fmt(p.start_3)} → ${fmt(p.end_3)}`))];
 h+=g.lente?`<p class="muted">Période à 3° : ${windows.join('<br>')}</p>`:`<p class="muted">Fenêtre à 1° : ${windows.join('<br>')}${g.planete==='Lune'?'':`<br>Période à 3° : ${broad.join('<br>')}`}</p>`;
 const exacts=[...new Set(g.contacts.flatMap(p=>p.exacts||[]).sort().map(fmt))];if(exacts.length)h+=`<p class="exact">${exacts.map(t=>'★ Exact : '+t).join('<br>')}</p>`;h+='</div></details>';const days=[selected,...calData.jours.filter(d=>d.date!==selected.date)];const day=days.find(d=>g.contacts.some(c=>overlaps(c,d)));const p=day&&g.contacts.find(c=>overlaps(c,day));if(p){const query=new URLSearchParams({date:day.date,contact_planete:p.planete,contact_point:p.point,contact_aspect:p.aspect});h+=`<p><a class="action" href="${escapeCal(calData.journal_url+'?'+query.toString())}">Noter ce que je vis en ce moment</a><br><small class="muted">Date de la note : ${escapeCal(new Intl.DateTimeFormat('fr-FR',{timeZone:calData.fuseau,day:'numeric',month:'long',year:'numeric'}).format(new Date(day.debut)))}</small></p>`;}return h+'</section>';
}
function detailCal(){let h;
 if(el('view')?.value==='sky'){
 const d=selected;
  h=`<h2>Ciel collectif · ${escapeCal(new Intl.DateTimeFormat('fr-FR',{timeZone:calData.fuseau,day:'numeric',month:'long'}).format(new Date(d.debut)))}</h2><p class="muted">Aspects actifs à moins de 3° d’orbe, indépendants de ton thème natal. ★ marque un passage exact calculé.</p>`;
  if(selectedSkyPeriod!==null){const p=skyPeriods[selectedSkyPeriod];h+=`<div class="cal-sky-detail ${skyClass(p)}"><strong>${escapeCal(p.titre)}</strong><p>Période à 3° : ${p.start?fmt(p.start):'déjà active avant le mois'} → ${p.end?fmt(p.end):'se poursuit après le mois'}</p>${p.exacts.length?`<p>${p.exacts.map(x=>'★ Exact : '+fmt(x)).join('<br>')}</p>`:'<p>Pas de passage exact pendant ce mois.</p>'}</div>`;}
  const stationnaires=skyStationOn(d.date);
  if(stationnaires.length)h+='<h3>Planètes stationnaires</h3><p class="muted">Jours où la vitesse devient très faible : au plus 20 % de la vitesse directe habituelle de cette planète.</p>'+stationnaires.map(p=>`<div class="cal-sky-detail sky-station ${skyMoverKind(p)}"><strong>${escapeCal(p.planete)} stationnaire</strong><p>${p.avant_mois?'Déjà stationnaire avant le mois · ': 'Du '+skyDate(p.debut)+' '}jusqu’au ${skyDate(p.fin)}${p.apres_mois?' (se poursuit après le mois)':''}. Changement de direction vers le mouvement ${escapeCal(p.direction)} le ${skyDate(p.changement)}.</p></div>`).join('');
  const retro=skyRetroOn(d.date);
  if(retro.length)h+='<h3>Rétrogradations en cours</h3>'+['personal','slow'].map(kind=>{const items=retro.filter(p=>skyMoverKind(p)===kind);return items.length?`<h4>${kind==='personal'?'Mercure, Vénus et Mars':'Jupiter à Pluton'}</h4>`+items.map(p=>`<div class="cal-sky-detail sky-station ${kind}"><strong>${escapeCal(p.planete)} rétrograde</strong><p>${p.avant_mois?'Déjà rétrograde au début du mois':'Depuis le '+skyDate(p.debut)} · ${p.apres_mois?'se poursuit après le mois':'jusqu’au '+skyDate(p.fin)}</p></div>`).join(''):''}).join('');
  const aspects=skyPeriodsOn(d);
  if(aspects.length)h+=[['Aspects du jour',aspects.filter(p=>!skyClimate(p))],['Climat de fond du ciel',aspects.filter(skyClimate)]].map(([titre,items])=>items.length?`<h3>${titre}</h3>`+items.map(p=>`<div class="cal-sky-detail ${skyClass(p)}"><strong>${escapeCal(p.titre)}</strong><p>Orbe inférieur ou égal à 3°${p.exacts.filter(x=>localKey(x)===d.date).length?' · ★ exact ce jour':''}</p></div>`).join(''):'').join('');
  const events=skyEventsOn(d.date);
  if(events.length)h+='<h3>Mouvements du jour</h3>'+events.map(e=>`<div class="cal-sky-detail ${skyClass(e)}"><strong>${escapeCal(skyEventLabel(e))}</strong><p>${e.station?'Changement de direction relevé ce jour':'Changement de signe relevé ce jour'}</p></div>`).join('');
  if(!aspects.length&&!events.length&&!retro.length&&!stationnaires.length)h+='<p class="muted">Aucun transit collectif retenu pour ce jour.</p>';
  if(checked('journal')){const notes=calData.notes.filter(n=>n.date===d.date);if(notes.length)h+='<h3>Mon journal</h3>'+notes.map(n=>`<div class="event"><p class="note">${escapeCal(n.texte)}</p><a href="${escapeCal(n.url)}">Lire mon observation</a></div>`).join('')}
  h+=`<p><a class="action" href="${escapeCal(calData.journal_url)}?date=${d.date}">Écrire pour cette date</a></p>`;
  el('detail').innerHTML=h;return;
 }
 if(selectedClimate){
  h='<h2>Climat de fond</h2><p class="muted">Contacts actifs sur les journées de cette bande. Choisis-en un pour afficher sa période seule.</p>'+selectedClimate.map(i=>`<button class="cal-focus-choice" data-focus="${i}">${escapeCal(groups[i].label)}</button>`).join('');
  el('detail').innerHTML=h;el('detail').querySelectorAll('[data-focus]').forEach(b=>b.onclick=()=>{focusedSlow=+b.dataset.focus;selectedGroup=focusedSlow;selectedClimate=null;drawCal()});return;
 }
 if(selectedGroup!==null){h=contactDetails(groups[selectedGroup]);h+='<p class="muted">Clique sur une date pour retrouver ton journal.</p>'}else{const d=selected;h=`<h2>${escapeCal(new Intl.DateTimeFormat('fr-FR',{timeZone:calData.fuseau,day:'numeric',month:'long'}).format(new Date(d.debut)))}</h2>`;
 if(checked('mars'))for(const g of groups.filter(g=>enabled(g)&&(g.lente?overlaps(g,d):visibleDay(g,d))))h+=contactDetails(g);
 for(const e of calData.events.filter(e=>eventVisible(e)&&localKey(e.date)===d.date))h+=`<div class="event"><strong>${escapeCal(e.label)}</strong>${fmt(e.date)}${stationDetails(e)}</div>`;
 if(checked('journal')){const notes=calData.notes.filter(n=>n.date===d.date);if(notes.length)h+='<h3>Mon journal</h3>'+notes.map(n=>`<div class="event"><p class="note">${escapeCal(n.texte)}</p><a href="${escapeCal(n.url)}">Lire mon observation</a></div>`).join('')}
 h+=`<p><a class="action" href="${escapeCal(calData.journal_url)}?date=${d.date}">Écrire pour cette date</a></p>`}el('detail').innerHTML=h;}
function drawCal(){
 const view=el('view')?.value||'personal';
 if(el('compact'))el('compact').hidden=view==='sky'||focusedSlow===null;
 if(el('personal-filters'))el('personal-filters').hidden=view==='sky';
 document.querySelector('.cal-view-selector')?.setAttribute('data-sky',view==='sky');
 if(el('instructions'))el('instructions').textContent=view==='sky'?'Les bandes montrent les aspects à 3° ; ★ marque le passage exact. Les stations sont des bandes continues. Les aspects entre Uranus, Neptune et Pluton sont regroupés dans le climat du ciel.':personalInstructions;
 if(el('view-help'))el('view-help').textContent={personal:calData.mars?'Les lentes dessinent le climat de fond. Soleil, Vénus et Mars sont retenus pour leur duo natal ou leur contact au maître d’Ascendant. Les passages de Mercure restent dans les contacts rapides.':'Ton journal et tes repères disponibles sont affichés ici.',rs:'Contacts faisant écho à un duo de la RS en cours impliquant Jupiter à Pluton. Ce ne sont pas des contacts directs aux positions de RS.',fast:'Soleil, Mercure, Vénus et Mars : tous les contacts calculés à 1°, sans filtre natal ou RS. Les quinconces et les contacts rapides aux nœuds restent exclus.',lunar:'Exploration facultative : les contacts lunaires à 1°, avec leurs horaires. Ils ne figurent pas dans les transits personnels.',sky:'Aspects collectifs à 3°, phases stationnaires calculées sur la vitesse de chaque planète, changements de signe et rétrogradations.'}[view];
 if(el('view-empty'))el('view-empty').textContent=view==='sky'?(calData.ciel_collectif?'':'Les calculs du ciel collectif sont momentanément indisponibles.'):groups.some(enabled)?'':(view==='rs'?'Aucun écho RS retenu pour ce mois avec les RS enregistrées et les filtres actuels.':'');
 let h='<div class="cal-weekdays">'+['Lun','Mar','Mer','Jeu','Ven','Sam','Dim'].map(x=>`<div class="weekday">${x}</div>`).join('')+'</div>';
 const cells=Array(calData.decalage).fill(null).concat(calData.jours);while(cells.length%7)cells.push(null);
 for(let w=0;w<cells.length;w+=7){const week=cells.slice(w,w+7);let bands=[];
 if(view==='sky'){
   skyPeriods.forEach((p,index)=>{if(skyClimate(p))return;const columns=week.map((d,i)=>d&&overlaps(p,d)?i:-1).filter(i=>i>=0);if(columns.length)bands.push({skyPeriod:p,index,first:columns[0],last:columns.at(-1)})});
   const climateDays=week.map(d=>d?skyPeriods.filter(p=>skyClimate(p)&&overlaps(p,d)):[]);
   for(let i=0;i<7;){if(!climateDays[i].length){i++;continue}const first=i;let periods=[];while(i<7&&climateDays[i].length){periods.push(...climateDays[i]);i++}bands.push({skyClimateGroup:[...new Set(periods)],first,last:i-1});}
   skyStations.forEach(p=>{const columns=week.map((d,i)=>d&&p.debut<=d.date&&d.date<=p.fin?i:-1).filter(i=>i>=0);if(columns.length)bands.push({skyStation:p,first:columns[0],last:columns.at(-1)})});
  for(const kind of ['personal','slow'])for(let i=0;i<7;){const daily=week[i]&&skyRetroOn(week[i].date).filter(p=>skyMoverKind(p)===kind);if(!daily?.length){i++;continue}const first=i;let retro=[];while(i<7&&week[i]){const active=skyRetroOn(week[i].date).filter(p=>skyMoverKind(p)===kind);if(!active.length)break;retro.push(...active);i++}bands.push({retroGroup:[...new Set(retro)],retroKind:kind,first,last:i-1});}
 }
 if(view!=='sky'&&checked('mars'))groups.forEach((g,index)=>{if(!enabled(g)||(g.lente&&focusedSlow!==index))return;const columns=week.map((d,i)=>d&&visibleDay(g,d)?i:-1).filter(i=>i>=0);if(columns.length)bands.push({g,index,first:columns[0],last:columns.at(-1)})});
 if(view!=='sky'&&focusedSlow===null&&checked('mars')){
  const perDay=week.map(d=>d?groups.map((g,index)=>({g,index})).filter(({g})=>g.lente&&enabled(g)&&overlaps(g,d)).map(x=>x.index):[]);
  for(let i=0;i<7;){if(!perDay[i].length){i++;continue}const first=i;let ids=[];while(i<7&&perDay[i].length){ids.push(...perDay[i]);i++}ids=[...new Set(ids)];const planets=new Set(ids.map(n=>groups[n].planete));bands.push({climate:ids,first,last:i-1,g:{label:'Climat de fond · '+planets.size+' planète'+(planets.size>1?'s':'')}});}
 }
 bands.sort((a,b)=>a.first-b.first||b.last-a.last);const stationPlanets=[...new Set(bands.filter(b=>b.skyStation).map(b=>b.skyStation.planete))];const retroKinds=['personal','slow'].filter(kind=>bands.some(b=>b.retroKind===kind));const skyClimateLane=bands.some(b=>b.skyClimateGroup)?stationPlanets.length+retroKinds.length:-1;const lanes=bands.some(b=>b.climate)?[6]:Array(stationPlanets.length+retroKinds.length+(skyClimateLane<0?0:1)).fill(6);
 for(const b of bands){if(b.climate){b.lane=0;continue}if(b.skyStation){b.lane=stationPlanets.indexOf(b.skyStation.planete);continue}if(b.retroGroup){b.lane=stationPlanets.length+retroKinds.indexOf(b.retroKind);continue}if(b.skyClimateGroup){b.lane=skyClimateLane;continue}let lane=lanes.findIndex(end=>end<b.first);if(lane<0)lane=lanes.length;lanes[lane]=b.last;b.lane=lane;}
 h+=`<div class="cal-week" style="--band-lanes:${Math.max(1,lanes.length)}">`;week.forEach((d,i)=>{if(!d){h+=`<div class="cal-blank" style="grid-column:${i+1};grid-row:1"></div>`;return}h+=`<button class="day ${d.date===localKey(new Date())?'today':''} ${d.date===selected.date&&selectedGroup===null?'selected':''}" style="grid-column:${i+1};grid-row:1" data-date="${d.date}" ${d.date===localKey(new Date())?'aria-current="date"':''} aria-label="${d.date}"><span class="num">${d.numero}${d.date===localKey(new Date())?'<small class="today-label">Aujourd’hui</small>':''}</span>`;h+=view==='sky'?skyEventsOn(d.date).filter(e=>!e.station).map(e=>`<span class="pill sky ${skyClass(e)}">${escapeCal(skyEventLabel(e))}</span>`).join(''):calData.events.filter(e=>eventVisible(e)&&localKey(e.date)===d.date).map(e=>`<span class="pill ${e.kind==='station'?'station':e.kind==='solar'?'solar':'moon'}">${escapeCal(e.label)}</span>`).join('');const n=calData.notes.filter(n=>n.date===d.date).length;if(checked('journal')&&n)h+=`<span class="pill journal">${n} note(s)</span>`;h+='</button>'});
 for(const b of bands){const {g,index,first,last,lane}=b;
 if(b.skyStation){const p=b.skyStation;const position=week.findIndex(d=>d?.date===p.changement);const marker=position>=first&&position<=last?`<span class="cal-star" style="left:${(position-first+.5)/(last-first+1)*100}%" title="${escapeCal(p.planete)} devient ${escapeCal(p.direction)} le ${skyDate(p.changement)}">${p.direction==='direct'?'D':'R'}</span>`:'';h+=`<button class="cal-band cal-sky-station ${skyMoverKind(p)}" style="grid-column:${first+1} / ${last+2};grid-row:1;--band-lane:${lane}" data-date="${position>=first&&position<=last?p.changement:week[first].date}" title="${escapeCal(p.planete)} stationnaire du ${skyDate(p.debut)} au ${skyDate(p.fin)}" aria-label="${escapeCal(p.planete)} stationnaire du ${skyDate(p.debut)} au ${skyDate(p.fin)}, devient ${escapeCal(p.direction)} le ${skyDate(p.changement)}"><span class="cal-band-label">${p.debut<week[first].date?'← ':''}${escapeCal(p.planete)} stationnaire${p.fin>week[last].date?' →':''}</span>${marker}</button>`;continue;}
 if(b.retroGroup){const planets=[...new Set(b.retroGroup.map(p=>p.planete))];h+=`<div class="cal-band cal-sky-retro ${b.retroKind}" style="grid-column:${first+1} / ${last+2};grid-row:1;--band-lane:${lane}" title="${escapeCal(planets.join(', '))} rétrograde${planets.length>1?'s':''}">${b.retroKind==='personal'?'Mercure · Vénus · Mars':'Jupiter à Pluton'} : ${escapeCal(planets.join(', '))} rétrograde${planets.length>1?'s':''}</div>`;continue;}
 if(b.skyClimateGroup){const count=b.skyClimateGroup.length;h+=`<button class="cal-band cal-sky-climate" style="grid-column:${first+1} / ${last+2};grid-row:1;--band-lane:${lane}" data-sky-climate title="${count} aspects entre Uranus, Neptune et Pluton : ${escapeCal(b.skyClimateGroup.map(p=>p.titre).join(', '))}">Climat du ciel · ${count} aspect${count>1?'s':''} <span aria-hidden="true">＋</span></button>`;continue;}
 if(b.skyPeriod){const p=b.skyPeriod;const exact=p.exacts.map(localKey);let stars='',firstStar=null;for(let i=first;i<=last;i++)if(exact.includes(week[i].date)){const pos=((i-first+.5)/(last-first+1))*100;if(firstStar===null)firstStar=pos;stars+=`<span class="cal-star" style="left:${pos}%" title="Passage exact le ${week[i].date}">★</span>`;}h+=`<button class="cal-band cal-sky-band ${skyClass(p)}" style="grid-column:${first+1} / ${last+2};grid-row:1;--band-lane:${lane}" data-sky-period="${index}" data-date="${week[first].date}" title="${escapeCal(p.titre)} · période à 3°"><span class="cal-band-label" style="${firstStar===null?'':`max-width:calc(${firstStar}% - 13px)`}">${p.start&&+new Date(p.start)<+new Date(week[first].debut)?'← ':''}${escapeCal(p.titre)}${p.end&&+new Date(p.end)>+new Date(week[last].fin)?' →':''}</span>${stars}</button>`;continue;}
 if(b.climate){h+=`<button class="cal-band cal-climate" style="grid-column:${first+1} / ${last+2};grid-row:1;--band-lane:${lane}" data-climate="${b.climate.join(',')}" aria-label="${escapeCal(g.label)} : accéder aux transits de fond du mois en cours">${escapeCal(g.label)} <span aria-hidden="true">＋</span></button>`;continue;}
const before=bounds(g)[0]<+new Date(week[first].debut),after=bounds(g)[1]>+new Date(week[last].fin);const exact=exactDays(g);let stars='';let firstStar=null;for(let i=first;i<=last;i++)if(exact.includes(week[i].date)){const pos=((i-first+.5)/(last-first+1))*100;if(firstStar===null)firstStar=pos;stars+=`<span class="cal-star" style="left:${pos}%" title="Passage exact le ${week[i].date}">★</span>`;}
 h+=`<button data-planet="${escapeCal(g.planete)}" class="cal-band ${g.maitre?'cal-ruler':''} ${g.lente?'cal-slow':''} ${before?'continues-before':''} ${after?'continues-after':''}" style="grid-column:${first+1} / ${last+2};grid-row:1;--band-lane:${lane}" data-group="${index}" title="${escapeCal(g.label)} · ${fmt(g.start)} → ${fmt(g.end)}" aria-label="${escapeCal(g.label)} du ${fmt(g.start)} au ${fmt(g.end)}${exact.length?', passage exact : '+exact.join(', '):''}"><span class="cal-band-label" style="${firstStar===null?'':`max-width:calc(${firstStar}% - 13px)`}">${before?'← ':''}${escapeCal(g.label)}${g.maitre?' · Maître d’Asc.':''}${after?' →':''}</span>${stars}</button>`}
 h+='</div>'}
 el('grid').innerHTML=h;el('grid').querySelectorAll('.day[data-date],.cal-sky-station[data-date]').forEach(b=>b.onclick=()=>{selected=calData.jours.find(d=>d.date===b.dataset.date);selectedGroup=null;selectedClimate=null;selectedSkyPeriod=null;drawCal()});el('grid').querySelectorAll('[data-sky-period]').forEach(b=>b.onclick=()=>{selected=calData.jours.find(d=>d.date===b.dataset.date);selectedSkyPeriod=+b.dataset.skyPeriod;drawCal()});el('grid').querySelectorAll('[data-group]').forEach(b=>b.onclick=()=>{selectedGroup=+b.dataset.group;selectedClimate=null;drawCal()});el('grid').querySelectorAll('[data-climate],[data-sky-climate]').forEach(b=>b.onclick=()=>{const panel=el('background');panel?.scrollIntoView?.({behavior:'smooth',block:'start'});panel?.focus?.({preventScroll:true})});if(el('periods'))el('periods').parentElement.hidden=view==='sky'||!checked('mars');drawPeriods();drawBackground();detailCal();}
function drawBackground(){
 const panel=el('background');if(!panel)return;
 if(el('view')?.value==='sky'){
  const entries=skyPeriods.map((p,index)=>({p,index})).filter(({p})=>skyClimate(p));
  panel.hidden=!entries.length;
  panel.setAttribute('aria-label','Climat du ciel du mois en cours');
  panel.innerHTML=entries.length?'<h2>Climat du ciel du mois en cours</h2><p class="muted">Aspects entre Uranus, Neptune et Pluton, actifs à 3° d’orbe. Clique pour voir leur période et leurs passages exacts.</p><div class="cal-background-list">'+entries.map(({p,index})=>`<button type="button" class="cal-background-contact" data-sky-background="${index}"><strong>${escapeCal(p.titre)}</strong><small>${p.start?fmt(p.start):'Déjà actif avant le mois'} → ${p.end?fmt(p.end):'Se poursuit après le mois'}</small></button>`).join('')+'</div>':'';
  panel.querySelectorAll('[data-sky-background]').forEach(button=>button.onclick=()=>{const index=+button.dataset.skyBackground;selected=calData.jours.find(d=>overlaps(skyPeriods[index],d))||calData.jours[0];selectedSkyPeriod=index;drawCal();el('detail')?.scrollIntoView?.({behavior:'smooth',block:'nearest'})});
  return;
 }
 const entries=groups.map((g,index)=>({g,index})).filter(({g})=>g.lente&&enabled(g));
 panel.setAttribute('aria-label','Transits de fond du mois en cours');
 panel.hidden=(el('view')?.value||'personal')!=='personal'||!checked('mars');
 if(panel.hidden){panel.innerHTML='';return}
 const card=({g,index})=>`<button type="button" class="cal-background-contact ${g.maitre?'cal-ruler':''}" data-planet="${escapeCal(g.planete)}" data-background="${index}"><strong>${escapeCal(g.label)}</strong>${g.maitre?'<small>Maître d’Ascendant natal</small>':''}<small>${g.start?fmt(g.start):'Déjà actif avant la fenêtre calculée'} → ${g.end?fmt(g.end):'Se poursuit après la fenêtre calculée'}</small></button>`;
 const row=(planets,secondary=false)=>{const columns=planets.map(planet=>{const items=entries.filter(({g})=>g.planete===planet);return items.length?'<div class="cal-background-planet">'+items.map(card).join('')+'</div>':''}).join('');return columns?`<div class="cal-background-list${secondary?' cal-background-list-secondary':''}">${columns}</div>`:''};
 panel.innerHTML='<h2>Les transits de fond du mois en cours</h2><p class="muted">Périodes actives à 3°. Clique sur un transit pour voir son détail et sa période dans le calendrier.</p>'+(entries.length?row(['Pluton','Uranus','Neptune'])+row(['Saturne','Jupiter'],true):'<p class="muted">Aucun transit de fond dans les filtres sélectionnés.</p>');
 panel.querySelectorAll('[data-background]').forEach(button=>button.onclick=()=>{selectedGroup=+button.dataset.background;focusedSlow=selectedGroup;selectedClimate=null;drawCal();el('detail')?.scrollIntoView?.({behavior:'smooth',block:'nearest'})});
}
function drawPeriods(){if(el('periods')){const first=new Date(calData.jours[0].debut),last=new Date(calData.jours.at(-1).fin);el('periods').innerHTML=groupContacts(calData.periods||[]).filter(enabled).map(g=>{const left=g.start?Math.max(0,(new Date(g.start)-first)/(last-first)*100):0,right=g.end?Math.min(100,(new Date(g.end)-first)/(last-first)*100):100;return `<div class="period" data-planet="${escapeCal(g.planete)}"><strong>${escapeCal(g.label)}</strong><div class="track"><span class="bar" style="left:${left}%;width:${right-left}%"></span></div><span class="muted">${fmt(g.start)} → ${fmt(g.end)}</span></div>`}).join('')}}
const monthPicker=el('month');if(monthPicker)monthPicker.addEventListener('change',()=>{if(monthPicker.value&&monthPicker.value!==monthPicker.defaultValue&&monthPicker.checkValidity())monthPicker.form.requestSubmit()});
if(el('compact'))el('compact').onclick=()=>{focusedSlow=null;selectedGroup=null;selectedClimate=null;drawCal()};
function syncCalendarView(){
 const view=el('view')?.value||'personal';
 if(el('affichage'))el('affichage').value=view;
 document.querySelectorAll('.cal .nav a').forEach(a=>{const url=new URL(a.href);url.searchParams.set('affichage',view);a.href=url.toString()});
}
['mars','moon','journal','view',...(calData.planetes_disponibles||[]).map(p=>'planet-'+p)].forEach(id=>{if(el(id))el(id).onchange=()=>{if(id==='view')syncCalendarView();focusedSlow=null;selectedGroup=null;selectedClimate=null;selectedSkyPeriod=null;drawCal()}});syncCalendarView();drawCal();
