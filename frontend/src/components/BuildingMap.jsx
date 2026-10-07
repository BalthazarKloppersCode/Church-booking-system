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

// DESIGN_DIRECTION.md §3 floor plan: four fills, nothing else.
//   free         white, navy outline, navy label
//   selected     navy fill, white label
//   booked       stone fill, grey outline, grey label + "booked"
//   unavailable  not bookable (corridors, stairs, toilets) — drawn, never labelled.
//                A room too large or too small for the group reuses this fill but
//                keeps its name so people can still tell which room it is.
// Colours live in index.css as tokens; this component only picks a state.
const STYLE = `
  .bm-shell{max-width:100%;font-family:inherit;color:var(--ink)}
  .bm-tabs{display:flex;gap:6px;background:var(--paper);padding:5px;border:1px solid var(--line);border-radius:12px;width:fit-content;margin-bottom:14px}
  .bm-tabs button{border:0;background:transparent;min-height:36px;padding:0 14px;border-radius:8px;font-weight:500;font-size:14px;cursor:pointer;color:var(--ink-2)}
  .bm-tabs button.active{background:var(--navy);color:#fff}
  .bm-card{background:var(--paper);border:1px solid var(--line);border-radius:12px;overflow:hidden;padding:16px}
  .bm-svg{width:100%;height:auto;display:block}
  .bm-floor{display:none} .bm-floor.active{display:block}

  .bm-room{stroke-width:1.4px;vector-effect:non-scaling-stroke;transition:fill .15s}
  .bm-room.state-free{fill:var(--paper);stroke:var(--navy);cursor:pointer}
  .bm-room.state-free:hover{fill:var(--hover)}
  .bm-room.state-selected{fill:var(--navy);stroke:var(--navy);cursor:pointer}
  .bm-room.state-booked,.bm-room.state-unavailable{stroke-width:1.2px;stroke:var(--plan-line);cursor:not-allowed}
  .bm-room.state-booked{fill:var(--plan-booked)}
  .bm-room.state-unavailable{fill:var(--plan-blocked)}
  .bm-room:focus-visible{outline:none;stroke-width:3px}
  .bm-space{fill:var(--plan-blocked);stroke:var(--plan-line);stroke-width:1.2px;vector-effect:non-scaling-stroke}

  .bm-label{pointer-events:none;text-anchor:middle;font-weight:600;font-size:22px;letter-spacing:.03em}
  .bm-label.small{font-size:15px}
  .bm-label.state-free{fill:var(--navy)}
  .bm-label.state-selected{fill:#fff}
  .bm-label.state-booked,.bm-label.state-unavailable{fill:var(--ink-3)}
  .bm-sublabel{pointer-events:none;text-anchor:middle;font-size:16px;fill:var(--ink-3)}
  .bm-sublabel.small{font-size:12px}
  .bm-sublabel.state-selected{fill:#fff;opacity:.8}

  .bm-legend{display:flex;gap:18px;flex-wrap:wrap;align-items:center;color:var(--ink-2);font-size:13px;margin-top:14px;padding-top:12px;border-top:1px solid var(--line-soft)}
  .bm-legend span{display:inline-flex;align-items:center}
  .bm-swatch{width:22px;height:15px;border-radius:3px;display:inline-block;margin-right:7px;border:1.2px solid var(--plan-line)}
  .bm-swatch.free{background:var(--paper);border:1.4px solid var(--navy)}
  .bm-swatch.selected{background:var(--navy);border-color:var(--navy)}
  .bm-swatch.booked{background:var(--plan-booked)}
  .bm-swatch.unavailable{background:var(--plan-blocked)}
`;

function roomState(suggestion, selectedRoomId) {
  if (!suggestion) return { state: 'unavailable' };
  if (selectedRoomId === suggestion.room.id) return { state: 'selected' };
  if (!suggestion.available) return { state: 'booked', note: 'booked' };
  // Too large for the group (more than 20% over the best-fitting option, for
  // anything other than a classroom/leap room) is a hard block, same as
  // already being booked — not just a soft "larger than you need" badge.
  if (suggestion.fit_quality === 'oversized') return { state: 'unavailable', note: 'too large' };
  return { state: 'free' };
}

function RoomShape({ mapName, points, path, textX, textY, textStyle, small, suggestions, selectedRoomId, onSelectRoom }) {
  const dbName = ROOM_NAME_MAP[mapName];
  const suggestion = suggestions.find((s) => s.room.name === dbName);
  const { state, note } = roomState(suggestion, selectedRoomId);
  const clickable = state === 'free' || state === 'selected';
  const stateText = { free: 'free', selected: 'selected', booked: 'already booked', unavailable: note || 'not available' }[state];

  const shapeProps = {
    className: `bm-room state-${state}`,
    role: 'button',
    tabIndex: clickable ? 0 : -1,
    'aria-label': `${dbName}, ${stateText}`,
    'aria-disabled': !clickable || undefined,
    onClick: clickable ? () => onSelectRoom(suggestion) : undefined,
    onKeyDown: clickable
      ? (e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onSelectRoom(suggestion);
          }
        }
      : undefined,
  };
  const sizeClass = small ? ' small' : '';
  const fontSize = textStyle?.fontSize;

  return (
    <g>
      {points ? <polygon {...shapeProps} points={points} /> : <path {...shapeProps} d={path} />}
      <text x={textX} y={textY} className={`bm-label state-${state}${sizeClass}`} style={textStyle}>{mapName.toUpperCase()}</text>
      {note && (
        <text x={textX} y={textY + (small ? 17 : (fontSize || 22) + 4)} className={`bm-sublabel state-${state}${sizeClass}`}>
          {note}
        </text>
      )}
    </g>
  );
}

export default function BuildingMap({ suggestions, onSelect }) {
  const [floor, setFloor] = useState('ground');
  const [activeInfo, setActiveInfo] = useState(null);
  const selectedRoomId = activeInfo?.room.id;

  function handleSelectRoom(suggestion) {
    setActiveInfo(suggestion);
  }

  function handleConfirmSelect() {
    if (activeInfo) onSelect(activeInfo);
  }

  const common = { suggestions, selectedRoomId, onSelectRoom: handleSelectRoom };

  return (
    <div className="bm-shell">
      <style>{STYLE}</style>

      <div className="bm-tabs">
        <button type="button" className={floor === 'ground' ? 'active' : ''} onClick={() => setFloor('ground')}>Ground floor</button>
        <button type="button" className={floor === 'upper' ? 'active' : ''} onClick={() => setFloor('upper')}>Upper floor</button>
      </div>

      <div className="bm-card">
        <svg className={`bm-svg bm-floor ${floor === 'ground' ? 'active' : ''}`} viewBox="0 0 1400 1300" role="group" aria-label="Ground floor plan">
          <polygon className="bm-space" points="330,800 1070,800 1060,410 1140,410 1280,410 1280,470 1120,460 1120,830 340,830 330,800" />

          <g transform="translate(30 360)">
            <polygon className="bm-space" points="100,280 295,280 295,465 100,465" />
          </g>
          <g transform="translate(30 330)">
            <polygon className="bm-space" points="295,280 425,278 425,465 295,465" />
          </g>
          <g transform="translate(30 330)">
            <polygon className="bm-space" points="425,278 548,270 548,465 425,465" />
          </g>

          <g transform="translate(30 330)">
            <RoomShape mapName="Kids 1" points="548,260 700,245 710,465 548,465" textX={628} textY={364} {...common} />
          </g>
          <g transform="translate(30 330)">
            <RoomShape mapName="Kids 2" points="700,245 862,231 872,465 710,465" textX={786} textY={355} {...common} />
          </g>
          <g transform="translate(30 330)">
            <RoomShape mapName="Kids 3" points="862,231 1028,216 1035,465 872,465" textX={950} textY={344} {...common} />
          </g>

          <g transform="translate(-20 10) rotate(-90 1075 417.5) translate(1075 417.5) scale(0.62) translate(-1075 -417.5)">
            <g className="bm-space">
              <path d="M1038 370 L1112 370 L1112 465 L1038 465 Z" />
              <line x1="1048" y1="383" x2="1102" y2="383" />
              <line x1="1048" y1="396" x2="1102" y2="396" />
              <line x1="1048" y1="409" x2="1102" y2="409" />
              <line x1="1048" y1="422" x2="1102" y2="422" />
              <line x1="1048" y1="435" x2="1102" y2="435" />
              <line x1="1048" y1="448" x2="1102" y2="448" />
            </g>
          </g>

          <g transform="translate(-20 10)">
            <RoomShape mapName="Kids 4" points="1115,320 1255,315 1265,395 1115,400" textX={1188} textY={362} small {...common} />
          </g>
          <g transform="translate(-20 10)">
            <RoomShape mapName="Kids 5" points="1115,240 1247,235 1255,315 1115,320" textX={1184} textY={282} small {...common} />
          </g>
          <g transform="translate(-20 10)">
            <RoomShape mapName="Leap 1" points="1115,160 1239,155 1247,235 1115,240" textX={1180} textY={202} small {...common} />
          </g>
          <g transform="translate(-20 10)">
            <RoomShape mapName="Leap 2" points="1115,80 1231,75 1239,155 1115,160" textX={1177} textY={122} small {...common} />
          </g>

          <g transform="translate(40 350)">
            <RoomShape mapName="Coffee Shop" path="M100 475 L300 475 L300 720 L100 720 Z" textX={200} textY={603} {...common} />
          </g>

          <g transform="translate(-20 270)">
            <RoomShape mapName="Main Hall" path="M365 565 L1115 565 L1115 730 L1080 775 L1015 805 L515 805 L450 785 L400 750 L365 700 Z" textX={745} textY={690} textStyle={{ fontSize: 30 }} {...common} />
          </g>
        </svg>

        <svg className={`bm-svg bm-floor ${floor === 'upper' ? 'active' : ''}`} viewBox="0 0 1400 1300" role="group" aria-label="Upper floor plan">
          <polygon className="bm-space" points="640,250 540,250 510,500 640,510 640,250 640,250" />

          <g transform="translate(20 -50)">
            <RoomShape mapName="Lounge" path="M130 245 L380 195 L515 270 L485 535 L205 570 L105 455 Z" textX={310} textY={385} textStyle={{ fontSize: 27 }} {...common} />
          </g>
          <g transform="translate(0 -40)">
            <RoomShape mapName="Training Hall" path="M645 225 L1090 225 L1140 300 L1125 545 L650 545 Z" textX={884} textY={385} textStyle={{ fontSize: 28 }} {...common} />
          </g>

          <g transform="translate(0 -190)">
            <rect className="bm-space" x="530" y="300" width="115" height="125" rx="5" />
          </g>

          <g transform="translate(0 -230) translate(594 500) scale(0.6) translate(-594 -500)">
            <g className="bm-space">
              <rect x="555" y="445" width="78" height="105" rx="4" />
              <line x1="565" y1="462" x2="623" y2="462" />
              <line x1="565" y1="478" x2="623" y2="478" />
              <line x1="565" y1="494" x2="623" y2="494" />
              <line x1="565" y1="510" x2="623" y2="510" />
              <line x1="565" y1="526" x2="623" y2="526" />
            </g>
          </g>
        </svg>

        <div className="bm-legend" aria-label="Floor plan key">
          <span><i className="bm-swatch free" />Free at your time</span>
          <span><i className="bm-swatch selected" />Selected</span>
          <span><i className="bm-swatch booked" />Already booked</span>
          <span><i className="bm-swatch unavailable" />Not bookable</span>
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
                <p style={{ fontSize: 13, color: 'var(--ink-2)' }}>{activeInfo.room.amenities.join(' · ')}</p>
              )}
              {activeInfo.room.description && (
                <p style={{ fontSize: 13, color: 'var(--ink-2)' }}>{activeInfo.room.description}</p>
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
