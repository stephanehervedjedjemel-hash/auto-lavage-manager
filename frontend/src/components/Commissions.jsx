import {useEffect,useState} from 'react'
import {api} from '../api'

const money=value=>Number(value||0).toLocaleString('fr-FR')+' FCFA'
const today=()=>new Date().toISOString().slice(0,10)

export default function Commissions({stations=[]}){
  const [employees,setEmployees]=useState([])
  const [services,setServices]=useState([])
  const [rules,setRules]=useState([])
  const [rows,setRows]=useState([])
  const [showRule,setShowRule]=useState(false)
  const [paying,setPaying]=useState(null)
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  async function load(){
    setBusy(true);setError('')
    try{
      const [staff,serviceList,ruleList,commissionList]=await Promise.all([
        api('/api/v1/employees'),api('/api/v1/services'),
        api('/api/v1/commission-rules'),api('/api/v1/commissions')
      ])
      setEmployees(staff);setServices(serviceList);setRules(ruleList);setRows(commissionList.items||[])
    }catch(e){setError(e.message)}finally{setBusy(false)}
  }
  useEffect(()=>{load()},[])
  async function createRule(e){
    e.preventDefault();const f=new FormData(e.currentTarget)
    const type=f.get('calculation_type')
    const payload={station_id:f.get('station_id')?Number(f.get('station_id')):null,
      employee_id:f.get('employee_id')?Number(f.get('employee_id')):null,
      service_id:f.get('service_id')?Number(f.get('service_id')):null,
      code:f.get('code'),name:f.get('name'),calculation_type:type,
      value:Number(f.get('value')),effective_from:f.get('effective_from'),
      effective_to:f.get('effective_to')||null}
    try{await api('/api/v1/commission-rules',{method:'POST',body:payload});setShowRule(false);await load()}
    catch(e){setError(e.message)}
  }
  async function pay(e){
    e.preventDefault();const f=new FormData(e.currentTarget)
    try{await api('/api/v1/commissions/'+paying+'/payments',{method:'POST',body:{
      amount:Number(f.get('amount')),method:f.get('method'),reference:f.get('reference')||null
    }});setPaying(null);await load()}
    catch(e){setError(e.message)}
  }
  const earned=rows.reduce((n,x)=>n+x.amount,0)
  const paid=rows.reduce((n,x)=>n+x.paid_amount,0)
  const remaining=rows.reduce((n,x)=>n+x.remaining_amount,0)
  return <><section className="cards">
    <article><small>COMMISSIONS ACQUISES</small><strong>{money(earned)}</strong><span>{rows.length} prestation(s) attribuée(s)</span></article>
    <article><small>COMMISSIONS RÉGLÉES</small><strong>{money(paid)}</strong><span>Versements enregistrés</span></article>
    <article><small>RESTE À RÉGLER</small><strong>{money(remaining)}</strong><span>Solde des laveurs</span></article>
    <article><small>BARÈMES ACTIFS</small><strong>{rules.filter(x=>x.is_active).length}</strong><span>Règles de calcul</span></article>
  </section>
  <section className="panel">
    <div className="panel-head"><div><h2>Barèmes de commissions</h2><p className="muted">Montant fixe par prestation ou taux en points de base : 1 000 = 10 %.</p></div>
      <div className="quick-actions"><button onClick={load} disabled={busy}>Actualiser</button><button className="primary" onClick={()=>setShowRule(!showRule)}>Nouveau barème</button></div>
    </div>
    {showRule&&<form className="inline-form" onSubmit={createRule}>
      <label>Code du barème<input name="code" required/></label>
      <label>Désignation<input name="name" required/></label>
      <label>Station<select name="station_id"><option value="">Toutes les stations</option>{stations.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      <label>Laveur<select name="employee_id"><option value="">Tous les laveurs</option>{employees.map(x=><option key={x.id} value={x.id}>{x.full_name}</option>)}</select></label>
      <label>Prestation<select name="service_id"><option value="">Toutes les prestations</option>{services.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
      <label>Type de calcul<select name="calculation_type"><option value="fixed">Montant fixe (FCFA / unité)</option><option value="percent">Pourcentage (points de base)</option></select></label>
      <label>Valeur<input name="value" type="number" min="1" step="1" required/></label>
      <label>Début d'application<input name="effective_from" type="date" defaultValue={today()} required/></label>
      <label>Fin d'application (facultatif)<input name="effective_to" type="date"/></label>
      <button className="primary">Enregistrer le barème</button><button type="button" onClick={()=>setShowRule(false)}>Annuler</button>
    </form>}
    <div className="table-wrap"><table><thead><tr><th>Code</th><th>Barème</th><th>Portée</th><th>Calcul</th><th>Valeur</th><th>Applicable du</th><th>État</th></tr></thead>
      <tbody>{rules.map(r=><tr key={r.id}><td>{r.code}</td><td>{r.name}</td><td>{r.employee_id?'Laveur ciblé':'Tous les laveurs'} · {r.service_id?'Prestation ciblée':'Toutes prestations'}</td><td>{r.calculation_type==='fixed'?'Fixe':'Pourcentage'}</td><td>{r.calculation_type==='fixed'?money(r.value):((r.value/100).toFixed(2)+' %')}</td><td>{r.effective_from}{r.effective_to?' au '+r.effective_to:''}</td><td>{r.is_active?'Actif':'Inactif'}</td></tr>)}
      {!rules.length&&<tr><td colSpan="7">Aucun barème enregistré.</td></tr>}</tbody></table></div>
  </section>
  <section className="panel"><div className="panel-head"><div><h2>Commissions par prestation</h2><p className="muted">Les montants sont figés à la création du ticket. Un changement de tarif ne modifie pas les anciennes commissions.</p></div></div>
    {error&&<div className="error">{error}</div>}
    <div className="table-wrap"><table><thead><tr><th>Date</th><th>Laveur</th><th>Prestation</th><th>Base</th><th>Commission</th><th>Réglé</th><th>Solde</th><th>État</th><th></th></tr></thead>
      <tbody>{rows.map(x=><tr key={x.id}><td>{String(x.earned_at||'').slice(0,10)}</td><td>{x.employee_name}</td><td>{x.service_name}<small>Ticket #{x.ticket_id}</small></td><td>{money(x.basis_amount)}</td><td>{money(x.amount)}</td><td>{money(x.paid_amount)}</td><td>{money(x.remaining_amount)}</td><td>{x.status==='paid'?'Réglée':x.status==='partial'?'Partielle':'À régler'}</td><td>{x.remaining_amount>0&&<button className="small-btn" onClick={()=>setPaying(x.id)}>Régler</button>}</td></tr>)}
      {!rows.length&&<tr><td colSpan="9">Aucune commission enregistrée. Affectez un laveur à une ligne de ticket et définissez un barème.</td></tr>}</tbody></table></div>
    {paying!==null&&<form className="inline-form" onSubmit={pay}><b>Règlement de la commission #{paying}</b>
      <label>Montant (FCFA)<input name="amount" type="number" min="1" max={rows.find(x=>x.id===paying)?.remaining_amount||1} required/></label>
      <label>Moyen de paiement<select name="method"><option value="cash">Espèces</option><option value="wave">Wave</option><option value="orange_money">Orange Money</option><option value="mtn_money">MTN Money</option><option value="moov_money">Moov Money</option><option value="bank_transfer">Virement</option><option value="other">Autre</option></select></label>
      <label>Référence<input name="reference"/></label><button className="primary">Valider le règlement</button><button type="button" onClick={()=>setPaying(null)}>Annuler</button>
    </form>}
  </section></>
}
