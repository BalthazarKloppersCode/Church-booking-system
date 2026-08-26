import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import BuildingMap from '../components/BuildingMap';

const ROOM_TYPES = [
  { value: '', label: 'Any room type' },
  { value: 'classroom', label: 'Classroom' },
  { value: 'training_hall', label: 'Training hall' },
  { value: 'main_hall', label: 'Main hall' },
  { value: 'coffee_shop', label: 'Coffee shop' },
  { value: 'lounge', label: 'Lounge' },
  { value: 'leap', label: 'Leap' },
];

function toLocalISOString(dateStr, timeStr) {
  // dateStr: '2026-08-20', timeStr: '14:00' -> ISO for backend
  return new Date(`${dateStr}T${timeStr}:00`).toISOString();
}

const FORCED_PRIVATE_PURPOSES = ['Wedding', 'Funeral / memorial'];

export default function BookPage() {
  const [step, setStep] = useState(0);
  const [bookingKind, setBookingKind] = useState(null); // 'church' | 'private'
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [search, setSearch] = useState({
    date: '',
    startTime: '10:00',
    endTime: '12:00',
    headcount: '',
    type: '',
  });
  const [suggestions, setSuggestions] = useState([]);
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [viewMode, setViewMode] = useState('list');
  const [mapSuggestions, setMapSuggestions] = useState(null);
  const [mapLoading, setMapLoading] = useState(false);

  const [form, setForm] = useState({
    requester_name: '',
    congregation: '',
    email: '',
    phone: '',
    purpose: '',
    purpose_other: '',
    notes: '',
  });

  const [result, setResult] = useState(null);

  const [congregationOptions, setCongregationOptions] = useState([]);
  const [bookerToken, setBookerToken] = useState(() => localStorage.getItem('booker_token') || '');
  const [bookerUser, setBookerUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('booker_user') || 'null');
    } catch {
      return null;
    }
  });
  const [loginForm, setLoginForm] = useState({ email: '', password: '' });
  const [loginError, setLoginError] = useState('');
  const [loginSubmitting, setLoginSubmitting] = useState(false);

  const [purposes, setPurposes] = useState([]);
  const [purposesLoaded, setPurposesLoaded] = useState(false);
  const forcedPrivate = FORCED_PRIVATE_PURPOSES.includes(form.purpose);
  const isPrivateEvent = bookingKind === 'private' || forcedPrivate;

  const [wantsLounge, setWantsLounge] = useState(false);
  const [loungeChecking, setLoungeChecking] = useState(false);
  const [loungeAvailable, setLoungeAvailable] = useState(null);
  const [loungeRoom, setLoungeRoom] = useState(null);

  useEffect(() => {
    api
      .listBookingPurposes()
      .then(setPurposes)
      .catch(() => {})
      .finally(() => setPurposesLoaded(true));
  }, []);

  // Which area governs approval comes from the booker's own account (set by
  // the admin in Manage Users) — they never have to pick it here, just their
  // congregation. Accounts with no area assigned yet (pre-dating that field)
  // see every active congregation instead of a filtered list.
  useEffect(() => {
    api
      .listCongregations(true, bookerUser?.area_id || null)
      .then(setCongregationOptions)
      .catch(() => setCongregationOptions([]));
  }, [bookerUser]);

  async function handleBookerLogin(e) {
    e.preventDefault();
    setLoginError('');
    setLoginSubmitting(true);
    try {
      const result = await api.bookerLogin(loginForm);
      localStorage.setItem('booker_token', result.access_token);
      localStorage.setItem('booker_user', JSON.stringify(result.user));
      setBookerToken(result.access_token);
      setBookerUser(result.user);
    } catch (err) {
      setLoginError(err.message);
    } finally {
      setLoginSubmitting(false);
    }
  }

  async function handleToggleLounge(checked) {
    setWantsLounge(checked);
    if (!checked) {
      setLoungeAvailable(null);
      setLoungeRoom(null);
      return;
    }
    setLoungeChecking(true);
    try {
      const start_time = toLocalISOString(search.date, search.startTime);
      const end_time = toLocalISOString(search.date, search.endTime);
      const results = await api.suggestRooms({ headcount: 1, start_time, end_time, type: 'lounge' });
      const lounge = results[0];
      setLoungeRoom(lounge ? lounge.room : null);
      setLoungeAvailable(lounge ? lounge.available : false);
    } catch {
      setLoungeAvailable(false);
      setLoungeRoom(null);
    } finally {
      setLoungeChecking(false);
    }
  }

  async function handleSearch(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const start_time = toLocalISOString(search.date, search.startTime);
      const end_time = toLocalISOString(search.date, search.endTime);
      const payload = {
        headcount: Number(search.headcount),
        start_time,
        end_time,
        ...(search.type ? { type: search.type } : {}),
      };
      const rooms = await api.suggestRooms(payload);
      setSuggestions(rooms);
      setMapSuggestions(null);
      setViewMode('list');
      setStep(2);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleShowMap() {
    setViewMode('map');
    if (mapSuggestions) return;
    setMapLoading(true);
    try {
      const start_time = toLocalISOString(search.date, search.startTime);
      const end_time = toLocalISOString(search.date, search.endTime);
      // Unfiltered by room type — the map should always show every room,
      // regardless of the type filter used for the list search.
      const rooms = await api.suggestRooms({ headcount: Number(search.headcount), start_time, end_time });
      setMapSuggestions(rooms);
    } catch (err) {
      setError(err.message);
    } finally {
      setMapLoading(false);
    }
  }

  function pickRoom(suggestion) {
    setSelectedRoom(suggestion);
    setStep(3);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const start_time = toLocalISOString(search.date, search.startTime);
      const end_time = toLocalISOString(search.date, search.endTime);
      const booking = await api.createBooking({
        room_id: selectedRoom.room.id,
        headcount: Number(search.headcount),
        start_time,
        end_time,
        ...form,
        is_private_event: isPrivateEvent,
      });

      let loungeBooking = null;
      let loungeError = null;
      if (wantsLounge && loungeAvailable && loungeRoom) {
        try {
          loungeBooking = await api.createBooking({
            room_id: loungeRoom.id,
            // The Lounge is overflow reception space, not the main event —
            // it doesn't need to fit the whole headcount, just its own capacity.
            headcount: Math.min(Number(search.headcount), loungeRoom.capacity),
            start_time,
            end_time,
            ...form,
            is_private_event: isPrivateEvent,
          });
        } catch (err) {
          loungeError = err.message;
        }
      }

      setResult({ ...booking, loungeBooking, loungeError });
      setStep(4);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (!bookerToken) {
    return (
      <div className="container" style={{ maxWidth: 480 }}>
        <div className="eyebrow">
          <Link to="/" style={{ color: 'inherit' }}>← Back home</Link>
        </div>
        <h1 style={{ marginBottom: 12 }}>Log in to book a room</h1>
        <p style={{ marginBottom: 24 }}>
          You need to be logged in to make a booking. This just proves you're allowed to — the
          booking's own contact details can still be for someone else, like whoever's actually
          hosting the event.
        </p>
        <form className="card" onSubmit={handleBookerLogin}>
          {loginError && <p style={{ color: 'var(--danger)', fontSize: 13, marginBottom: 10 }}>{loginError}</p>}
          <div className="field">
            <label>Email</label>
            <input
              type="email"
              required
              value={loginForm.email}
              onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Password</label>
            <input
              type="password"
              required
              value={loginForm.password}
              onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
            />
          </div>
          <button className="btn btn-primary btn-block" disabled={loginSubmitting}>
            {loginSubmitting ? 'Logging in…' : 'Log in'}
          </button>
        </form>
        <p style={{ fontSize: 13, color: 'var(--ink-soft)', marginTop: 16 }}>
          Don't have an account? Contact the admin office to get one set up.
        </p>
      </div>
    );
  }

  return (
    <div className="container" style={{ maxWidth: 640 }}>
      <div className="eyebrow">
        <Link to="/" style={{ color: 'inherit' }}>← Back home</Link>
      </div>
      <h1 style={{ marginBottom: 30 }}>Book a room</h1>

      {error && (
        <div className="card" style={{ background: 'var(--danger-tint)', border: 'none', marginBottom: 20 }}>
          <p style={{ color: 'var(--danger)', margin: 0 }}>{error}</p>
        </div>
      )}

      {step === 0 && (
        <div className="card">
          <h3 style={{ marginBottom: 16 }}>What kind of booking is this?</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ padding: '18px 20px', textAlign: 'left', justifyContent: 'flex-start', height: 'auto' }}
              onClick={() => {
                setBookingKind('church');
                setStep(1);
              }}
            >
              <div>
                <div style={{ fontSize: 15, fontWeight: 600 }}>Church / congregation activity</div>
                <p style={{ fontSize: 13, margin: '4px 0 0' }}>
                  Services, meetings, or ministry activities. Confirmed instantly within two weeks out —
                  otherwise sent for a quick approval.
                </p>
              </div>
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ padding: '18px 20px', textAlign: 'left', justifyContent: 'flex-start', height: 'auto' }}
              onClick={() => {
                setBookingKind('private');
                setStep(1);
              }}
            >
              <div>
                <div style={{ fontSize: 15, fontWeight: 600 }}>Private event</div>
                <p style={{ fontSize: 13, margin: '4px 0 0' }}>
                  Weddings, funerals, or other non-congregation events. Always sent to the admin
                  office for approval first.
                </p>
              </div>
            </button>
          </div>
        </div>
      )}

      {step === 1 && (
        <form className="card" onSubmit={handleSearch}>
          <button
            type="button"
            className="btn btn-ghost"
            style={{ padding: '0 0 14px', color: 'var(--ink-soft)', fontSize: 13 }}
            onClick={() => setStep(0)}
          >
            ← Change booking type
          </button>
          <div className="field">
            <label>Date</label>
            <input
              type="date"
              required
              value={search.date}
              onChange={(e) => setSearch({ ...search, date: e.target.value })}
            />
          </div>
          <div className="field-row">
            <div className="field">
              <label>Start time</label>
              <input
                type="time"
                required
                value={search.startTime}
                onChange={(e) => setSearch({ ...search, startTime: e.target.value })}
              />
            </div>
            <div className="field">
              <label>End time</label>
              <input
                type="time"
                required
                value={search.endTime}
                onChange={(e) => setSearch({ ...search, endTime: e.target.value })}
              />
            </div>
          </div>
          <div className="field-row">
            <div className="field">
              <label>How many people?</label>
              <input
                type="number"
                min="1"
                required
                placeholder="e.g. 25"
                value={search.headcount}
                onChange={(e) => setSearch({ ...search, headcount: e.target.value })}
              />
            </div>
            <div className="field">
              <label>Room type</label>
              <select
                value={search.type}
                onChange={(e) => setSearch({ ...search, type: e.target.value })}
              >
                {ROOM_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
          </div>
          <button className="btn btn-primary btn-block" disabled={loading}>
            {loading ? 'Finding rooms…' : 'Find available rooms'}
          </button>
        </form>
      )}

      {step === 2 && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 18, gap: 12 }}>
            <p style={{ margin: 0 }}>
              Rooms that fit {search.headcount} people on {search.date} from {search.startTime}–{search.endTime}:
            </p>
            <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
              <button
                type="button"
                className={viewMode === 'list' ? 'btn btn-primary' : 'btn btn-secondary'}
                style={{ padding: '6px 12px', fontSize: 12 }}
                onClick={() => setViewMode('list')}
              >
                List
              </button>
              <button
                type="button"
                className={viewMode === 'map' ? 'btn btn-primary' : 'btn btn-secondary'}
                style={{ padding: '6px 12px', fontSize: 12 }}
                onClick={() => handleShowMap()}
              >
                Map
              </button>
            </div>
          </div>

          {viewMode === 'map' ? (
            mapLoading ? (
              <p>Loading map…</p>
            ) : (
              <BuildingMap suggestions={mapSuggestions || []} onSelect={pickRoom} />
            )
          ) : (
            <>
          {suggestions.length === 0 && (
            <p>No rooms match that size. Try adjusting the headcount or room type.</p>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {suggestions.map((s) => (
              <div key={s.room.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h3 style={{ fontSize: 17 }}>{s.room.name}</h3>
                  <p style={{ fontSize: 13 }}>
                    Capacity {s.room.capacity} · {s.room.type.replace('_', ' ')}
                    {s.room.location ? ` · ${s.room.location}` : ''}
                  </p>
                  {s.room.amenities?.length > 0 && (
                    <p style={{ fontSize: 13, color: 'var(--ink-soft)' }}>{s.room.amenities.join(' · ')}</p>
                  )}
                  {s.room.description && (
                    <p style={{ fontSize: 13, color: 'var(--ink-soft)' }}>{s.room.description}</p>
                  )}
                  {!s.available && (
                    <span className="badge badge-rejected">Already booked at this time</span>
                  )}
                  {s.available && s.fit_quality === 'oversized' && (
                    <span className="badge badge-cancelled">Larger than you need</span>
                  )}
                  {s.available && s.fit_quality === 'too_small' && (
                    <span className="badge badge-pending">Below your headcount</span>
                  )}
                </div>
                <button
                  className="btn btn-primary"
                  disabled={!s.available}
                  onClick={() => pickRoom(s)}
                >
                  Select
                </button>
              </div>
            ))}
          </div>
            </>
          )}
          <button className="btn btn-ghost" style={{ marginTop: 20 }} onClick={() => setStep(1)}>
            ← Change search
          </button>
        </div>
      )}

      {step === 3 && selectedRoom && (
        <form className="card" onSubmit={handleSubmit}>
          <h3 style={{ marginBottom: 16 }}>Booking {selectedRoom.room.name}</h3>
          <div className="field">
            <label>Your name</label>
            <input
              required
              value={form.requester_name}
              onChange={(e) => setForm({ ...form, requester_name: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Congregation / group</label>
            {congregationOptions.length === 0 ? (
              <p style={{ fontSize: 13, color: 'var(--danger)' }}>
                No congregations set up yet — ask the admin office.
              </p>
            ) : (
              <select
                required
                value={form.congregation}
                onChange={(e) => setForm({ ...form, congregation: e.target.value })}
              >
                <option value="" disabled>Select your congregation / group</option>
                {congregationOptions.map((c) => (
                  <option key={c.id} value={c.name}>{c.name}</option>
                ))}
              </select>
            )}
          </div>
          <div className="field-row">
            <div className="field">
              <label>Email</label>
              <input
                type="email"
                required
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            <div className="field">
              <label>WhatsApp number</label>
              <input
                required
                placeholder="+27 82 123 4567"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </div>
          </div>
          <div className="field">
            <label>What's this booking for?</label>
            {purposesLoaded && purposes.length === 0 ? (
              <p style={{ fontSize: 13, color: 'var(--danger)' }}>
                No booking purposes have been set up yet — ask the admin office to add one before booking.
              </p>
            ) : (
              <select
                required
                value={form.purpose}
                onChange={(e) =>
                  setForm({
                    ...form,
                    purpose: e.target.value,
                    purpose_other: e.target.value === 'Other' ? form.purpose_other : '',
                  })
                }
              >
                <option value="" disabled>Select a purpose</option>
                {purposes.map((p) => (
                  <option key={p.id} value={p.name}>{p.name}</option>
                ))}
              </select>
            )}
            {form.purpose === 'Other' && (
              <input
                required
                placeholder="Briefly describe the purpose"
                style={{ marginTop: 8 }}
                value={form.purpose_other}
                onChange={(e) => setForm({ ...form, purpose_other: e.target.value })}
              />
            )}
          </div>

          {selectedRoom.room.type === 'training_hall' && (
            <div className="field">
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  style={{ width: 'auto' }}
                  checked={wantsLounge}
                  onChange={(e) => handleToggleLounge(e.target.checked)}
                />
                Also book the Lounge as a separate reception area for this event
              </label>
              {wantsLounge && loungeChecking && (
                <p style={{ fontSize: 13 }}>Checking Lounge availability…</p>
              )}
              {wantsLounge && !loungeChecking && loungeAvailable === false && (
                <p style={{ fontSize: 13, color: 'var(--danger)' }}>
                  The Lounge is already booked for this time slot — it won't be included with this booking.
                </p>
              )}
              {wantsLounge && !loungeChecking && loungeAvailable === true && (
                <p style={{ fontSize: 13, color: 'var(--success)' }}>
                  The Lounge is free for this time — it will be booked alongside {selectedRoom.room.name}.
                </p>
              )}
            </div>
          )}

          <div className="field">
            <label>Anything else the admin office should know? (optional)</label>
            <textarea
              rows={2}
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </div>

          {isPrivateEvent && (
            <div className="card" style={{ background: 'var(--amber-tint)', border: 'none', marginBottom: 18 }}>
              <p style={{ color: 'var(--amber)', margin: 0, fontSize: 13 }}>
                {bookingKind === 'private'
                  ? "This is a private event, so it always needs admin approval before it's confirmed."
                  : "Weddings and funerals always need admin approval before they're confirmed."}
              </p>
            </div>
          )}

          <div style={{ display: 'flex', gap: 10 }}>
            <button type="button" className="btn btn-secondary" onClick={() => setStep(2)}>
              ← Back
            </button>
            <button className="btn btn-primary" style={{ flex: 1 }} disabled={loading}>
              {loading ? 'Submitting…' : 'Submit booking'}
            </button>
          </div>
        </form>
      )}

      {step === 4 && result && (
        <div className="card">
          {result.status === 'approved' ? (
            <>
              <span className="badge badge-approved" style={{ marginBottom: 12 }}>Confirmed</span>
              <h3>You're all set.</h3>
              <p>
                {result.room_name} is booked for {new Date(result.start_time).toLocaleString()}.
                A confirmation with room setup instructions has been sent to your email and WhatsApp.
              </p>
            </>
          ) : (
            <>
              <span className="badge badge-pending" style={{ marginBottom: 12 }}>Pending approval</span>
              <h3>Request sent to the admin office.</h3>
              <p>
                We'll notify you by email and WhatsApp as soon as it's reviewed
                {result.is_private_event ? ' — private events always need a quick approval.' : ' — bookings more than two weeks out need a quick approval.'}
              </p>
            </>
          )}
          {result.loungeBooking && (
            <p style={{ marginTop: 10, fontSize: 14 }}>
              The Lounge has also been {result.loungeBooking.status === 'approved' ? 'confirmed' : 'requested'} as reception space for the same time.
            </p>
          )}
          {result.loungeError && (
            <p style={{ marginTop: 10, fontSize: 14, color: 'var(--danger)' }}>
              Couldn't book the Lounge for reception ({result.loungeError}) — please contact the admin office to arrange it separately.
            </p>
          )}
          <Link to="/" className="btn btn-secondary" style={{ marginTop: 10 }}>Back home</Link>
        </div>
      )}
    </div>
  );
}
