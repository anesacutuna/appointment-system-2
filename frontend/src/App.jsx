import { useEffect, useMemo, useState } from 'react';
import React from 'react';
const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const authToken = () => localStorage.getItem('appointment_token');

async function request(path, options = {}) {
  const headers = { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(authToken() ? { Authorization: `Bearer ${authToken()}` } : {}), ...options.headers };
  const response = await fetch(`${API}${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || 'Došlo je do greške. Pokušaj ponovo.');
  }
  return response.status === 204 ? null : response.json();
}

function localDateString(date) {
  const y = date.getFullYear(); const m = String(date.getMonth() + 1).padStart(2, '0'); const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function App() {
  const [user, setUser] = useState(null);
  const [services, setServices] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [adminServices, setAdminServices] = useState([]);
  const [adminEmployees, setAdminEmployees] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [adminTab, setAdminTab] = useState('appointments');
  const [serviceId, setServiceId] = useState('');
  const [employeeId, setEmployeeId] = useState('');
  const [day, setDay] = useState(localDateString(new Date()));
  const [slots, setSlots] = useState([]);
  const [selectedSlot, setSelectedSlot] = useState('');
  const [view, setView] = useState('booking');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const chosenService = useMemo(() => services.find(item => String(item.id) === serviceId), [services, serviceId]);
  const chosenEmployee = useMemo(() => employees.find(item => String(item.id) === employeeId), [employees, employeeId]);

  async function loadPublicData() {
    try {
      const [serviceRows, employeeRows] = await Promise.all([request('/services'), request('/employees')]);
      setServices(serviceRows); setEmployees(employeeRows);
      if (!serviceId && serviceRows.length) setServiceId(String(serviceRows[0].id));
      if (!employeeId && employeeRows.length) setEmployeeId(String(employeeRows[0].id));
    } catch (e) { setError(e.message); }
  }

  async function loadAppointments(current = user) {
    if (!current) return;
    try { setAppointments(current.role === 'admin' ? await request('/admin/appointments') : await request('/appointments/me')); }
    catch (e) { setError(e.message); }
  }

  async function loadAdminData() {
    try {
      const [serviceRows, employeeRows, stats] = await Promise.all([request('/admin/services'), request('/admin/employees'), request('/admin/statistics')]);
      setAdminServices(serviceRows); setAdminEmployees(employeeRows); setStatistics(stats);
    } catch (e) { setError(e.message); }
  }

  async function createService(event) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    try {
      await request('/admin/services', { method: 'POST', body: JSON.stringify({ name: data.get('name'), description: data.get('description') || null, duration_minutes: Number(data.get('duration_minutes')), is_active: true }) });
      form.reset(); setNotice('Usluga je dodana.'); await loadAdminData(); await loadPublicData();
    } catch (e) { setError(e.message); }
  }

  async function toggleService(service) {
    try { await request(`/admin/services/${service.id}`, { method: 'PATCH', body: JSON.stringify({ name: service.name, description: service.description, duration_minutes: service.duration_minutes, is_active: !service.is_active }) }); await loadAdminData(); await loadPublicData(); }
    catch (e) { setError(e.message); }
  }

  async function createEmployee(event) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    try { await request('/admin/employees', { method: 'POST', body: JSON.stringify({ full_name: data.get('full_name'), is_active: true }) }); form.reset(); setNotice('Zaposlenik je dodan.'); await loadAdminData(); await loadPublicData(); }
    catch (e) { setError(e.message); }
  }

  async function toggleEmployee(employee) {
    try { await request(`/admin/employees/${employee.id}`, { method: 'PATCH', body: JSON.stringify({ full_name: employee.full_name, is_active: !employee.is_active }) }); await loadAdminData(); await loadPublicData(); }
    catch (e) { setError(e.message); }
  }

  async function saveWorkingHours(employeeId, event) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    try { await request(`/admin/employees/${employeeId}/working-hours`, { method: 'PUT', body: JSON.stringify({ weekday: Number(data.get('weekday')), start_time: data.get('start_time'), end_time: data.get('end_time'), is_working: true }) }); setNotice('Radno vrijeme je sačuvano.'); }
    catch (e) { setError(e.message); }
  }

  async function addDayOff(employeeId, event) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    try { await request(`/admin/employees/${employeeId}/exceptions`, { method: 'POST', body: JSON.stringify({ exception_date: data.get('exception_date'), is_closed: true, note: data.get('note') || null }) }); form.reset(); setNotice('Neradni dan je dodan.'); }
    catch (e) { setError(e.message); }
  }

  useEffect(() => { loadPublicData(); }, []);
  useEffect(() => {
    if (!authToken()) return;
    request('/auth/me').then(setUser).catch(() => localStorage.removeItem('appointment_token'));
  }, []);
  useEffect(() => { if (user) loadAppointments(user); }, [user]);
  useEffect(() => {
    setSlots([]); setSelectedSlot('');
    if (!serviceId || !employeeId || !day) return;
    request(`/availability?service_id=${serviceId}&employee_id=${employeeId}&date=${day}`)
      .then(result => setSlots(result.slots)).catch(e => setError(e.message));
  }, [serviceId, employeeId, day]);

  async function signIn(event) {
    event.preventDefault(); setError(''); setNotice('');
    const data = new FormData(event.currentTarget);
    try {
      const body = new URLSearchParams({ username: data.get('email'), password: data.get('password') });
      const response = await fetch(`${API}/auth/token`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body });
      const result = await response.json(); if (!response.ok) throw new Error(result.detail || 'Prijava nije uspjela.');
      localStorage.setItem('appointment_token', result.access_token); setUser(result.user); setView(result.user.role === 'admin' ? 'admin' : 'booking'); setNotice('Uspješno ste prijavljeni.');
    } catch (e) { setError(e.message); }
  }

  async function register(event) {
    event.preventDefault(); setError(''); setNotice('');
    const data = new FormData(event.currentTarget);
    try {
      await request('/auth/register', { method: 'POST', body: JSON.stringify({ full_name: data.get('full_name'), email: data.get('email'), password: data.get('password') }) });
      setNotice('Nalog je napravljen. Sada se prijavi.'); setView('login');
    } catch (e) { setError(e.message); }
  }

  async function book() {
    if (!selectedSlot) return;
    setBusy(true); setError(''); setNotice('');
    try {
      await request('/appointments', { method: 'POST', body: JSON.stringify({ service_id: Number(serviceId), employee_id: Number(employeeId), start_at: selectedSlot }) });
      setNotice('Termin je uspješno rezervisan.'); setSelectedSlot('');
      const result = await request(`/availability?service_id=${serviceId}&employee_id=${employeeId}&date=${day}`); setSlots(result.slots);
      await loadAppointments();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function cancel(id) {
    try { await request(`/appointments/${id}/cancel`, { method: 'POST' }); setNotice('Rezervacija je otkazana.'); await loadAppointments(); }
    catch (e) { setError(e.message); }
  }

  function signOut() {
    localStorage.removeItem('appointment_token'); setUser(null); setAppointments([]); setView('booking'); setNotice('Odjavljeni ste.');
  }

  return <main className="page-shell">
    <header className="topbar">
      <a className="brand" href="#home" onClick={e => { e.preventDefault(); setView('booking'); }}><span className="brand-mark">T</span><span>termini<span className="brand-dot">.</span><small>ONLINE REZERVACIJE</small></span></a>
      <nav>{user ? <><button className={view === 'booking' ? 'nav-active' : ''} onClick={() => setView('booking')}>Rezerviši</button>{user.role === 'client' && <button className={view === 'appointments' ? 'nav-active' : ''} onClick={() => { setView('appointments'); loadAppointments(); }}>Moji termini</button>}{user.role === 'admin' && <button className={view === 'admin' ? 'nav-active' : ''} onClick={() => { setView('admin'); loadAppointments(); loadAdminData(); }}>Administracija</button>}<button className="user-pill" onClick={signOut}>{user.full_name} · Odjava</button></> : <><button onClick={() => setView('login')}>Prijava</button><button className="nav-cta" onClick={() => setView('register')}>Kreiraj nalog</button></>}</nav>
    </header>

    <section className="hero"><div className="hero-copy"><div className="eyebrow"><span></span> JEDNOSTAVNO ZAKAZIVANJE</div><h1>Vaše vrijeme.<br /><em>Vaš termin.</em></h1><p>Pronađite uslugu, odaberite vrijeme koje vam odgovara i rezervišite termin za nekoliko trenutaka.</p><div className="hero-note"><span>✦</span> Dostupnost se ažurira u stvarnom vremenu</div></div><div className="hero-art"><div className="art-orbit orbit-one"></div><div className="art-orbit orbit-two"></div><div className="calendar-card"><div className="calendar-head"><span>VAŠ RASPORED</span><b>•••</b></div><div className="calendar-month">Novembar <span>2026</span></div><div className="calendar-grid calendar-days">{['P','U','S','Č','P','S','N'].map((x,i)=><span key={i}>{x}</span>)}</div><div className="calendar-grid calendar-dates">{[26,27,28,29,30,31,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15].map((x,i)=><span className={i === 11 ? 'selected-date' : ''} key={i}>{x}</span>)}</div><div className="calendar-appointment"><i></i><span>Slobodan termin</span><b>10:30</b></div></div><div className="art-spark spark-one">✳</div><div className="art-spark spark-two">✦</div><div className="art-caption">Lako. Jasno. Bez čekanja.</div></div></section>

    {(notice || error) && <div className={`flash ${error ? 'flash-error' : ''}`} role="status">{error || notice}<button onClick={() => { setNotice(''); setError(''); }}>×</button></div>}

    <section className="content-grid">
      <div className="booking-card">
        <div className="card-heading"><div><div className="eyebrow">REZERVACIJA</div><h2>Odaberite svoj termin</h2></div><div className="step-count"><b>01</b><span> / 03</span></div></div>
        <div className="steps"><div className="step-current"><i>1</i><span>Detalji</span></div><div className="step-line"></div><div className={selectedSlot ? 'step-current' : ''}><i>2</i><span>Vrijeme</span></div><div className="step-line"></div><div><i>3</i><span>Potvrda</span></div></div>
        <div className="form-grid"><label>Usluga<select value={serviceId} onChange={e => setServiceId(e.target.value)}><option value="">Odaberite uslugu</option>{services.map(s => <option value={s.id} key={s.id}>{s.name} · {s.duration_minutes} min</option>)}</select></label><label>Zaposlenik<select value={employeeId} onChange={e => setEmployeeId(e.target.value)}><option value="">Odaberite zaposlenika</option>{employees.map(x => <option value={x.id} key={x.id}>{x.full_name}</option>)}</select></label><label className="date-label">Datum<input type="date" min={localDateString(new Date())} value={day} onChange={e => setDay(e.target.value)} /></label></div>
        <div className="availability-header"><div><h3>Dostupna vremena</h3><p>{day ? new Date(`${day}T12:00:00`).toLocaleDateString('bs-BA', { weekday: 'long', day: 'numeric', month: 'long' }) : 'Odaberite datum'}</p></div><span className="timezone">Europe/Sarajevo</span></div>
        {!user && <div className="signin-callout"><span>◉</span><p>Za potvrdu rezervacije potrebna je prijava.</p><button onClick={() => setView('login')}>Prijavi se</button></div>}
        {user?.role === 'admin' && <div className="signin-callout"><span>ℹ</span><p>Administratorski nalog ne može praviti klijentske rezervacije.</p></div>}
        <div className="slot-grid">{slots.length ? slots.map(slot => <button key={slot} className={`slot ${selectedSlot === slot ? 'slot-selected' : ''}`} onClick={() => setSelectedSlot(slot)}>{new Date(slot).toLocaleTimeString('bs-BA', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Sarajevo' })}</button>) : <div className="empty-slots">{serviceId && employeeId ? 'Nema slobodnih termina za odabrani datum.' : 'Odaberite uslugu i zaposlenika da vidite dostupnost.'}</div>}</div>
        <div className="booking-footer"><div className="selection-summary">{selectedSlot ? <><span>Odabrali ste</span><b>{chosenService?.name} · {new Date(selectedSlot).toLocaleTimeString('bs-BA', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Sarajevo' })}</b></> : <span>Odaberite dostupno vrijeme</span>}</div><button className="primary-button" disabled={!selectedSlot || !user || user.role !== 'client' || busy} onClick={book}>{busy ? 'Rezervišem…' : 'Potvrdi rezervaciju'} <span>↗</span></button></div>
      </div>
      <aside className="side-card"><div className="side-icon">◷</div><h3>Rezervacija<br />bez komplikacija</h3><p>Sve dostupne termine vidite na jednom mjestu. Sistem automatski provjerava raspored i sprječava dvostruke rezervacije.</p><div className="side-divider"></div><div className="side-feature"><span>✓</span><div><b>Jasna dostupnost</b><small>Aktuelni termini zaposlenika</small></div></div><div className="side-feature"><span>✓</span><div><b>Brza potvrda</b><small>Rezervacija na nekoliko klikova</small></div></div><div className="side-feature"><span>✓</span><div><b>Jednostavno otkazivanje</b><small>Upravljajte svojim terminima</small></div></div><div className="side-footnote">VAŠ RASPORED, NA JEDNOM MJESTU</div></aside>
    </section>

    {(view === 'login' || view === 'register') && <div className="modal-backdrop" onClick={() => setView('booking')}><section className="auth-card" onClick={e => e.stopPropagation()}><button className="modal-close" onClick={() => setView('booking')}>×</button><div className="eyebrow">{view === 'login' ? 'DOBRO DOŠLI NAZAD' : 'NOVI KORISNIČKI NALOG'}</div><h2>{view === 'login' ? 'Prijavite se' : 'Kreirajte nalog'}</h2><p>{view === 'login' ? 'Prijavite se da upravljate svojim terminima.' : 'Registrujte se i rezervišite svoj prvi termin.'}</p><form onSubmit={view === 'login' ? signIn : register}>{view === 'register' && <label>Ime i prezime<input name="full_name" required minLength="2" placeholder="Vaše ime i prezime" /></label>}<label>Email adresa<input name="email" type="email" required placeholder="ime@email.com" /></label><label>Lozinka<input name="password" type="password" required minLength="8" placeholder="Najmanje 8 znakova" /></label><button className="primary-button auth-submit">{view === 'login' ? 'Prijavi se' : 'Napravi nalog'} <span>↗</span></button></form><div className="auth-switch">{view === 'login' ? 'Nemate nalog?' : 'Već imate nalog?'} <button onClick={() => setView(view === 'login' ? 'register' : 'login')}>{view === 'login' ? 'Registrujte se' : 'Prijavite se'}</button></div></section></div>}

    {(view === 'appointments' || view === 'admin') && user && <section className="appointments-card"><div className="card-heading"><div><div className="eyebrow">{view === 'admin' ? 'ADMINISTRACIJA' : 'MOJ PROFIL'}</div><h2>{view === 'admin' ? (adminTab === 'appointments' ? 'Pregled rezervacija' : 'Postavke organizacije') : 'Moji termini'}</h2></div><button className="refresh-button" onClick={() => view === 'admin' ? (loadAppointments(), loadAdminData()) : loadAppointments()}>Osvježi ↻</button></div>
      {view === 'admin' && <div className="admin-tabs"><button className={adminTab === 'appointments' ? 'admin-tab-active' : ''} onClick={() => setAdminTab('appointments')}>Rezervacije</button><button className={adminTab === 'services' ? 'admin-tab-active' : ''} onClick={() => { setAdminTab('services'); loadAdminData(); }}>Usluge</button><button className={adminTab === 'employees' ? 'admin-tab-active' : ''} onClick={() => { setAdminTab('employees'); loadAdminData(); }}>Zaposlenici i raspored</button></div>}
      {view === 'admin' && adminTab === 'appointments' && statistics && <div className="stats-grid">{[['Aktivni termini',statistics.active_appointments],['Danas',statistics.today_appointments],['Predstojeći',statistics.upcoming_appointments],['Otkazani',statistics.cancelled_appointments]].map(([label,value])=><div className="stat-card" key={label}><span>{label}</span><b>{value}</b></div>)}</div>}
      {(view === 'appointments' || (view === 'admin' && adminTab === 'appointments')) && (appointments.length ? <div className="appointment-list">{appointments.map(a => <article className="appointment-row" key={a.id}><div className="appointment-date"><b>{new Date(a.start_at).toLocaleDateString('bs-BA', { day: '2-digit', timeZone: 'Europe/Sarajevo' })}</b><span>{new Date(a.start_at).toLocaleDateString('bs-BA', { month: 'short', timeZone: 'Europe/Sarajevo' })}</span></div><div className="appointment-info"><b>{a.service_name || services.find(s => s.id === a.service_id)?.name || 'Usluga'}</b><span>{a.employee_name || employees.find(x => x.id === a.employee_id)?.full_name || 'Zaposlenik'} · {new Date(a.start_at).toLocaleTimeString('bs-BA', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Sarajevo' })}{a.client_name ? ` · ${a.client_name}` : ''}</span></div><span className={`status-badge ${a.status === 'cancelled' ? 'status-cancelled' : ''}`}>{a.status === 'cancelled' ? 'Otkazano' : 'Rezervisano'}</span>{a.status === 'booked' && <button className="cancel-button" onClick={() => cancel(a.id)}>Otkaži</button>}</article>)}</div> : <div className="empty-appointments">Još nema rezervacija za prikaz.</div>)}
      {view === 'admin' && adminTab === 'services' && <div className="admin-content"><form className="admin-form" onSubmit={createService}><h3>Dodaj uslugu</h3><label>Naziv<input name="name" required minLength="2" /></label><label>Trajanje (minute)<input name="duration_minutes" type="number" min="5" max="480" defaultValue="30" required /></label><label>Opis<textarea name="description" rows="2" /></label><button className="primary-button">Sačuvaj uslugu <span>↗</span></button></form><div className="admin-list"><h3>Usluge</h3>{adminServices.map(s => <div className="admin-list-row" key={s.id}><div><b>{s.name}</b><small>{s.duration_minutes} min{s.description ? ` · ${s.description}` : ''}</small></div><button className="toggle-button" onClick={() => toggleService(s)}>{s.is_active ? 'Aktivna' : 'Neaktivna'}</button></div>)}</div></div>}
      {view === 'admin' && adminTab === 'employees' && <div className="admin-content admin-employee-content"><form className="admin-form" onSubmit={createEmployee}><h3>Dodaj zaposlenika</h3><label>Ime i prezime<input name="full_name" required minLength="2" /></label><button className="primary-button">Dodaj zaposlenika <span>↗</span></button></form>{adminEmployees.map(employee => <article className="employee-admin-card" key={employee.id}><h3>{employee.full_name}<button className="toggle-button" onClick={() => toggleEmployee(employee)}>{employee.is_active ? 'Deaktiviraj' : 'Aktiviraj'}</button></h3><form className="hours-form" onSubmit={event => saveWorkingHours(employee.id, event)}><label>Dan<select name="weekday" defaultValue="0">{['Ponedjeljak','Utorak','Srijeda','Četvrtak','Petak','Subota','Nedjelja'].map((d,i)=><option value={i} key={i}>{d}</option>)}</select></label><label>Od<input name="start_time" type="time" defaultValue="09:00" required /></label><label>Do<input name="end_time" type="time" defaultValue="17:00" required /></label><button className="small-action">Sačuvaj radno vrijeme</button></form><form className="hours-form dayoff-form" onSubmit={event => addDayOff(employee.id, event)}><label>Neradni datum<input name="exception_date" type="date" min={localDateString(new Date())} required /></label><label>Napomena<input name="note" placeholder="npr. godišnji odmor" /></label><button className="small-action">Dodaj neradni dan</button></form></article>)}</div>}
    </section>}

    <footer className="footer"><span>© 2026 TERMINI</span><span>JEDNOSTAVNO ZAKAZIVANJE, BOLJA ORGANIZACIJA</span><span>MADE FOR YOUR TIME <b>✦</b></span></footer>
  </main>;
}

export default App;
