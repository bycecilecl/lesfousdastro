/* Only closed vocabularies leave this module. Never pass forms, errors or URLs. */
(() => {
    const read = key => { try { return sessionStorage.getItem(key); } catch (_) { return null; } };
    const write = (key, value) => { try { sessionStorage.setItem(key, value); } catch (_) {} };
    const sid = read('fda_session') || crypto.randomUUID();
    write('fda_session', sid);
    const query = new URLSearchParams(location.search);
    const pick = (value, allowed, fallback) => allowed.includes(value) ? value : fallback;
    const source = pick(query.get('utm_source') || read('fda_source'), ['instagram','google','newsletter','direct','other'], query.has('utm_source') ? 'other' : 'direct');
    const campaign = pick(query.get('utm_campaign') || read('fda_campaign'), ['free_analysis','free_j1','free_j3','free_j5','other'], 'other');
    write('fda_source', source); write('fda_campaign', campaign);
    const products = {flash_astral:25, forces_defis:15, point_astral_famille:42, flash_transits:19, profil_amoureux:25, analyse_karmique:69, clarification_questions:25, pack_essence:49, pack_origines:83, pack_integral:109};
    const events = ['funnel_visit','free_analysis_start','free_analysis_success','free_analysis_error','free_analysis_close','paid_offer_click','offer_view','view_item','add_to_cart','begin_checkout','checkout_error','offer_feedback'];
    const offered = 'flash_astral'; // Baseline A only; no experiment activated.
    write('fda_offer', offered);
    function track(event, input = {}) {
        if (!events.includes(event)) return;
        if (event === 'offer_view') write('fda_offer_exposed', '1');
        const data = {event, session_id:sid, offered_product:offered, source, campaign, device:matchMedia('(max-width: 767px)').matches ? 'mobile':'desktop'};
        if (Object.hasOwn(products, input.product)) { data.product=input.product; data.price=products[input.product]; }
        for (const [key, allowed] of Object.entries({location:['home','free_result','catalog','cart','stripe','paypal'], reason:['enough','choice','sample','price','personalization','not_ready','other'], error_type:['generation','quota','network','payment','validation'],stage:['loading','success','error']})) {
            if (allowed.includes(input[key])) data[key]=input[key];
        }
        if (event === 'offer_feedback') {
            for (const key of Object.keys(data)) if (!['event','session_id','offered_product','reason'].includes(key)) delete data[key];
        }
        fetch('/api/conversion/events', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),keepalive:true}).catch(() => {});
        const {event:_, session_id, ...params} = data;
        params.funnel_session_id = session_id;
        if (data.product) { params.currency='EUR'; params.value=data.price; params.items=[{item_id:data.product,price:data.price,quantity:1}]; }
        if (read('fda_debug') === '1') params.debug_mode=true;
        window.gtag?.('event', event, params);
    }
    window.fdaTrack = track;
    document.addEventListener('DOMContentLoaded', () => {
        if (location.pathname === '/') track('funnel_visit', {location:'home'});
        const observer = new IntersectionObserver(entries => entries.forEach(entry => {
            if (entry.isIntersecting) { track('view_item', {product:entry.target.id,location:'catalog'}); observer.unobserve(entry.target); }
        }), {threshold:0.5});
        Object.keys(products).forEach(key => { const card=document.getElementById(key); if (card) observer.observe(card); });
        if (location.pathname === '/traiter-analyses') {
            fetch('/api/conversion/purchase', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:sid,offered_product:read('fda_offer_exposed') === '1' ? offered : undefined})})
            .then(r => r.ok && r.status !== 204 ? r.json() : null).then(data => {
                if (!data || read('purchase_'+data.transaction_id)) return;
                if (data.sandbox && read('fda_debug') !== '1') return; // Test orders never enter production GA revenue.
                const {sandbox, ...params} = data;
                window.gtag?.('event','purchase',{...params,funnel_session_id:sid,source,campaign,...(read('fda_debug') === '1' ? {debug_mode:true} : {})});
                write('purchase_'+data.transaction_id,'1');
            }).catch(() => {});
        }
    });
})();
