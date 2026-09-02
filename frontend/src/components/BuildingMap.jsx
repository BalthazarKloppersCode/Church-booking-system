import { useState } from 'react';

// Maps the floor-plan SVG's room labels to the real room names in the database.
const ROOM_NAME_MAP = {
  'Kids 1': 'Kids Classroom 1',
  'Kids 2': 'Kids Classroom 2',
  'Kids 3': 'Kids Classroom 3',
  'Kids 4': 'Kids Classroom 4',
  'Kids 5': 'Kids Classroom 5',
  'Leap 1': 'Leap Classroom 1',
  'Leap 2': 'Leap Classroom 2',
  'Coffee Shop': 'Coffee Shop',
  'Main Hall': 'Main Hall',
  'Lounge': 'Lounge',
  'Training Hall': 'Training Hall',
};

const STYLE = `
  .bm-shell{max-width:100%;font-family:inherit;color:var(--ink)}
  .bm-tabs{display:flex;gap:8px;background:var(--surface);padding:6px;border-radius:12px;box-shadow:var(--shadow);width:fit-content;margin-bottom:14px}
  .bm-tabs button{border:0;background:transparent;padding:8px 14px;border-radius:8px;font-weight:600;font-size:13px;cursor:pointer;color:var(--ink)}
  .bm-tabs button.active{background:var(--teal-dark);color:#fff}
  .bm-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden;padding:16px}
  .bm-svg{width:100%;height:auto;display:block;border-radius:12px;background:linear-gradient(145deg,#f7f4ee,#ece9e3)}
  .bm-floor{display:none} .bm-floor.active{display:block}
  .bm-room-shape{stroke:#353b43;stroke-width:3;vector-effect:non-scaling-stroke;transition:.15s}
  .bm-room-shape.clickable{cursor:pointer}
  .bm-room-shape.clickable:hover{filter:brightness(1.08)}
  .bm-room-shape.selected{stroke:#fff;stroke-width:6}
  .bm-room-shape.unavailable{filter:grayscale(0.85) brightness(0.95);cursor:not-allowed}
  .bm-support{fill:#b7b7b4;opacity:.82;stroke:#353b43;stroke-width:3;vector-effect:non-scaling-stroke}
  .bm-corridor{fill:#e6ddd0;stroke:#353b43;stroke-width:3;vector-effect:non-scaling-stroke}
  .bm-label{pointer-events:none;text-anchor:middle;fill:#fff;font-weight:800;font-size:22px;text-shadow:0 2px 5px rgba(0,0,0,.4)}
  .bm-label.dark{fill:#333;text-shadow:none}
  .bm-label.small{font-size:15px}
  .bm-legend{display:flex;gap:14px;flex-wrap:wrap;align-items:center;color:var(--ink-soft);font-size:12px;margin-top:12px}
  .bm-dot{width:11px;height:11px;border-radius:3px;display:inline-block;margin-right:5px}
`;

function RoomShape({ mapName, points, path, textX, textY, textStyle, labelClass, suggestions, selectedRoomId, onSelectRoom, fill }) {
  const dbName = ROOM_NAME_MAP[mapName];
  const suggestion = suggestions.find((s) => s.room.name === dbName);
  // Too large for the group (more than 20% over the best-fitting option, for
  // anything other than a classroom/leap room) is a hard block, same as
  // already being booked — not just a soft "larger than you need" badge.
  const blocked = !suggestion || !suggestion.available || suggestion.fit_quality === 'oversized';
  const clickable = !!suggestion && !blocked;
  const isSelected = suggestion && selectedRoomId === suggestion.room.id;

  const classes = ['bm-room-shape'];
  if (clickable) classes.push('clickable');
  if (blocked) classes.push('unavailable');
  if (isSelected) classes.push('selected');

  const shapeProps = {
    className: classes.join(' '),
    fill,
    onClick: clickable ? () => onSelectRoom(suggestion) : undefined,
  };

  return (
    <g>
      {points ? <polygon {...shapeProps} points={points} /> : <path {...shapeProps} d={path} />}
      <text x={textX} y={textY} className={labelClass} style={textStyle}>{mapName.toUpperCase()}</text>
    </g>
  );
}

export default function BuildingMap({ suggestions, onSelect }) {
  const [floor, setFloor] = useState('ground');
  const [activeInfo, setActiveInfo] = useState(null);

  function handleSelectRoom(suggestion) {
    setActiveInfo(suggestion);
  }

  function handleConfirmSelect() {
    if (activeInfo) onSelect(activeInfo);
  }

  return (
    <div className="bm-shell">
      <style>{STYLE}</style>

      <div className="bm-tabs">
        <button type="button" className={floor === 'ground' ? 'active' : ''} onClick={() => setFloor('ground')}>Ground Floor</button>
        <button type="button" className={floor === 'upper' ? 'active' : ''} onClick={() => setFloor('upper')}>Upper Floor</button>
      </div>

      <div className="bm-card">
        <svg className={`bm-svg bm-floor ${floor === 'ground' ? 'active' : ''}`} viewBox="0 0 1400 1300">
          <defs>
            <linearGradient id="bm-mainGrad" x1="0" x2="1"><stop stopColor="#474a4f" /><stop offset="1" stopColor="#303338" /></linearGradient>
            <linearGradient id="bm-coffeeGrad" x1="0" x2="1"><stop stopColor="#ad7a49" /><stop offset="1" stopColor="#8a582f" /></linearGradient>
            <linearGradient id="bm-blueGrad" x1="0" x2="1"><stop stopColor="#4a7bb7" /><stop offset="1" stopColor="#355f96" /></linearGradient>
            <linearGradient id="bm-greenGrad" x1="0" x2="1"><stop stopColor="#789660" /><stop offset="1" stopColor="#587347" /></linearGradient>
          </defs>

          <polygon className="bm-corridor" points="330,800 1070,800 1060,410 1140,410 1280,410 1280,470 1120,460 1120,830 340,830 330,800" />

          <g transform="translate(30 360)">
            <polygon className="bm-support" points="100,280 295,280 295,465 100,465" />
            <text x="197" y="365" className="bm-label dark small">TODDLERS ROOM</text>
          </g>
          <g transform="translate(30 330)">
            <polygon className="bm-support" points="295,280 425,278 425,465 295,465" />
            <text x="360" y="355" className="bm-label dark small">MOM'S ROOM</text>
          </g>
          <g transform="translate(30 330)">
            <polygon className="bm-support" points="425,278 548,270 548,465 425,465" />
            <text x="486" y="365" className="bm-label dark small">ROOM</text>
          </g>

          <g transform="translate(30 330)">
            <RoomShape mapName="Kids 1" points="548,260 700,245 710,465 548,465" textX={628} textY={364} labelClass="bm-label" fill="url(#bm-blueGrad)" suggestions={suggestions} selectedRoomId={activeInfo?.room.id} onSelectRoom={handleSelectRoom} />
          </g>
          <g transform="translate(30 330)">
            <RoomShape mapName="Kids 2" points="700,245 862,231 872,465 710,465" textX={786} textY={355} labelClass="bm-label" fill="url(#bm-blueGrad)" suggestions={suggestions} selectedRoomId={activeInfo?.room.id} onSelectRoom={handleSelectRoom} />
          </g>
          <g transform="translate(30 330)">
            <RoomShape mapName="Kids 3" points="862,231 1028,216 1035,465 872,465" textX={950} textY={344} labelClass="bm-label" fill="url(#bm-blueGrad)" suggestions={suggestions} selectedRoomId={activeInfo?.room.id} onSelectRoom={handleSelectRoom} />
          </g>

          <g transform="translate(-20 10) rotate(-90 1075 417.5) translate(1075 417.5) scale(0.62) translate(-1075 -417.5)">
            <g fill="#d5d1ca" stroke="#353b43" strokeWidth="3">
              <path d="M1038 370 L1112 370 L1112 465 L1038 465 Z" />
              <line x1="1048" y1="383" x2="1102" y2="383" />
              <line x1="1048" y1="396" x2="1102" y2="396" />
              <line x1="1048" y1="409" x2="1102" y2="409" />
              <line x1="1048" y1="422" x2="1102" y2="422" />
              <line x1="1048" y1="435" x2="1102" y2="435" />
              <line x1="1048" y1="448" x2="1102" y2="448" />
            </g>
            <text x="1075" y="350" className="bm-label dark small">STAIRS</text>
          </g>

          <g transform="translate(-20 10)">
            <RoomShape mapName="Leap 1" points="1115,320 1255,315 1265,395 1115,400" textX={1188} textY={362} labelClass="bm-label small" fill="url(#bm-greenGrad)" suggestions={suggestions} selectedRoomId={activeInfo?.room.id} onSelectRoom={handleSelectRoom} />
          </g>
          <g transform="translate(-20 10)">
            <RoomShape mapName="Leap 2" points="1115,240 1247,235 1255,315 1115,320" textX={1184} textY={282} labelClass="bm-label small" fill="url(#bm-greenGrad)" suggestions={suggestions} selectedRoomId={activeInfo?.room.id} onSelectRoom={handleSelectRoom} />
          </g>
          <g transform="translate(-20 10)">
            <RoomShape mapName="Kids 4" points="1115,160 1239,155 1247,235 1115,240" textX={1180} textY={202} labelClass="bm-label small" fill="url(#bm-blueGrad)" suggestions={suggestions} selectedRoomId={activeInfo?.room.id} onSelectRoom={handleSelectRoom} />
          </g>
          <g transform="translate(-20 10)">
            <RoomShape mapName="Kids 5" points="1115,80 1231,75 1239,155 1115,160" textX={1177} textY={122} labelClass="bm-label small" fill="url(#bm-blueGrad)" suggestions={suggestions} selectedRoomId={activeInfo?.room.id} onSelectRoom={handleSelectRoom} />
          </g>

          <g transform="translate(40 350)">
            <RoomShape mapName="Coffee Shop" path="M100 475 L300 475 L300 720 L100 720 Z" textX={200} textY={603} labelClass="bm-label" fill="url(#bm-coffeeGrad)" suggestions={suggestions} selectedRoomId={activeInfo?.room.id} onSelectRoom={handleSelectRoom} />
          </g>

          <g transform="translate(-20 270)">
            <RoomShape mapName="Main Hall" path="M365 565 L1115 565 L1115 730 L1080 775 L1015 805 L515 805 L450 785 L400 750 L365 700 Z" textX={745} textY={690} labelClass="bm-label" textStyle={{ fontSize: 30 }} fill="url(#bm-mainGrad)" suggestions={suggestions} selectedRoomId={activeInfo?.room.id} onSelectRoom={handleSelectRoom} />
          </g>
        </svg>

        <svg className={`bm-svg bm-floor ${floor === 'upper' ? 'active' : ''}`} viewBox="0 0 1400 1300">
          <defs>
            <linearGradient id="bm-loungeGrad" x1="0" x2="1"><stop stopColor="#b27b43" /><stop offset="1" stopColor="#8f5b31" /></linearGradient>
            <linearGradient id="bm-trainGrad" x1="0" x2="1"><stop stopColor="#746092" /><stop offset="1" stopColor="#584771" /></linearGradient>
          </defs>

          <polygon className="bm-corridor" points="640,250 540,250 510,500 640,510 640,250 640,250" />

          <g transform="translate(20 -50)">
            <RoomShape mapName="Lounge" path="M130 245 L380 195 L515 270 L485 535 L205 570 L105 455 Z" textX={310} textY={385} labelClass="bm-label" textStyle={{ fontSize: 27 }} fill="url(#bm-loungeGrad)" suggestions={suggestions} selectedRoomId={activeInfo?.room.id} onSelectRoom={handleSelectRoom} />
          </g>
          <g transform="translate(0 -40)">
            <RoomShape mapName="Training Hall" path="M645 225 L1090 225 L1140 300 L1125 545 L650 545 Z" textX={884} textY={385} labelClass="bm-label" textStyle={{ fontSize: 28 }} fill="url(#bm-trainGrad)" suggestions={suggestions} selectedRoomId={activeInfo?.room.id} onSelectRoom={handleSelectRoom} />
          </g>

          <g transform="translate(0 -190)">
            <rect x="530" y="300" width="115" height="125" rx="5" fill="#cbd9e4" stroke="#353b43" strokeWidth="3" />
            <text x="587" y="366" className="bm-label dark small">TOILETS</text>
          </g>

          <g transform="translate(0 -230) translate(594 500) scale(0.6) translate(-594 -500)">
            <g fill="#d5d1ca" stroke="#353b43" strokeWidth="3">
              <rect x="555" y="445" width="78" height="105" rx="4" />
              <line x1="565" y1="462" x2="623" y2="462" />
              <line x1="565" y1="478" x2="623" y2="478" />
              <line x1="565" y1="494" x2="623" y2="494" />
              <line x1="565" y1="510" x2="623" y2="510" />
              <line x1="565" y1="526" x2="623" y2="526" />
            </g>
            <text x="594" y="575" className="bm-label dark small">STAIRS</text>
          </g>
        </svg>

        <div className="bm-legend">
          <span><i className="bm-dot" style={{ background: '#4a7bb7' }} />Kids rooms</span>
          <span><i className="bm-dot" style={{ background: '#789660' }} />Leap rooms</span>
          <span><i className="bm-dot" style={{ background: '#9b6838' }} />Coffee shop</span>
          <span><i className="bm-dot" style={{ background: '#584771' }} />Training hall / Lounge</span>
          <span><i className="bm-dot" style={{ background: '#b7b7b4' }} />Not bookable</span>
        </div>
      </div>

      {activeInfo && (
        <div className="card" style={{ marginTop: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <h3 style={{ fontSize: 17 }}>{activeInfo.room.name}</h3>
              <p style={{ fontSize: 13 }}>
                Capacity {activeInfo.room.capacity} · {activeInfo.room.type.replace('_', ' ')}
                {activeInfo.room.location ? ` · ${activeInfo.room.location}` : ''}
              </p>
              {activeInfo.room.amenities?.length > 0 && (
                <p style={{ fontSize: 13, color: 'var(--ink-soft)' }}>{activeInfo.room.amenities.join(' · ')}</p>
              )}
              {activeInfo.room.description && (
                <p style={{ fontSize: 13, color: 'var(--ink-soft)' }}>{activeInfo.room.description}</p>
              )}
              {!activeInfo.available && (
                <span className="badge badge-rejected">Already booked at this time</span>
              )}
              {activeInfo.available && activeInfo.fit_quality === 'oversized' && (
                <span className="badge badge-cancelled">Too large for your group — pick a smaller room</span>
              )}
              {activeInfo.fit_quality === 'too_small' && (
                <span className="badge badge-pending">Below your headcount</span>
              )}
            </div>
            <button
              className="btn btn-primary"
              disabled={!activeInfo.available || activeInfo.fit_quality === 'oversized'}
              onClick={handleConfirmSelect}
            >
              Select
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
