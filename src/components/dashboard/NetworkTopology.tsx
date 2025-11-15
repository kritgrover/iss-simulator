import { useEffect, useState, useRef, useMemo } from 'react';
import { Card } from '@/components/ui/card';
import { DTNBundle } from '@/types/dtnBundle';
import { GroundStation } from '@/types/groundStation';

interface ActiveTransmission {
  bundle_id: string;
  bundle_id_short: string;
  from_station: string;
  to_station: string;
  progress_percent: number;
}

interface MeshConnection {
  from: string;
  to: string;
}

interface NetworkTopologyProps {
  stations: GroundStation[];
  meshConnections: MeshConnection[];
  activeTransmissions: ActiveTransmission[];
  dtnQueues: Record<string, DTNBundle[]>;
  activeStationId?: string | null;
}

type LinkState = 'default' | 'transmitting' | 'completed' | 'waiting_iss' | 'transmitting_iss' | 'all_complete';

interface LinkStateData {
  state: LinkState;
  bundleId: string;
  timestamp: number;
}

const NetworkTopology = ({
  stations,
  meshConnections,
  activeTransmissions,
  dtnQueues,
  activeStationId,
}: NetworkTopologyProps) => {
  const [linkStates, setLinkStates] = useState<Map<string, LinkStateData>>(new Map());
  const [blinkState, setBlinkState] = useState(false);
  const completedTransmissionsRef = useRef<Set<string>>(new Set());
  const previousTransmissionsRef = useRef<Set<string>>(new Set());
  const previousLinkStatesRef = useRef<Map<string, LinkStateData>>(new Map());

  // Blink animation for waiting_iss state
  useEffect(() => {
    const interval = setInterval(() => {
      setBlinkState((prev) => !prev);
    }, 500); // Blink every 500ms
    return () => clearInterval(interval);
  }, []);

  // Calculate node positions (ISS in center, stations in circle)
  const nodePositions = useMemo(() => {
    const positions = new Map<string, { x: number; y: number }>();
    const centerX = 200;
    const centerY = 200;
    const radius = 140;

    // ISS in center
    positions.set('iss', { x: centerX, y: centerY });

    // Stations in circle
    stations.forEach((station, index) => {
      const angle = (index * 2 * Math.PI) / stations.length - Math.PI / 2; // Start from top
      const x = centerX + radius * Math.cos(angle);
      const y = centerY + radius * Math.sin(angle);
      positions.set(station.id, { x, y });
    });

    return positions;
  }, [stations]);

  // Track completed transmissions and update link states
  useEffect(() => {
    const currentTransmissionIds = new Set(activeTransmissions.map((t) => t.bundle_id));
    const newCompleted = new Set<string>();

    // Find transmissions that just completed
    previousTransmissionsRef.current.forEach((id) => {
      if (!currentTransmissionIds.has(id)) {
        newCompleted.add(id);
      }
    });

    // Update link states based on active transmissions
    const newLinkStates = new Map<string, LinkStateData>();
    const now = Date.now();

    // Process active transmissions
    activeTransmissions.forEach((transmission) => {
      const from = transmission.from_station.toLowerCase();
      const to = transmission.to_station.toLowerCase();
      const linkKey = `${from}-${to}`;
      const isIssLink = to === 'iss' || from === 'iss';

      // Get bundle to check route and status
      const bundle = Object.values(dtnQueues)
        .flat()
        .find((b) => b.bundle_id === transmission.bundle_id);

      if (bundle) {
        const route = bundle.route || bundle.hops || [];
        const isDelivered = bundle.status === 'DELIVERED';

        // Check if this is the last ground station before ISS
        if (isIssLink && route.length >= 2) {
          const lastGroundStation = route[route.length - 2]?.toLowerCase();
          const isLastStation = from === lastGroundStation;

          if (isDelivered) {
            // All bundles delivered to ISS
            newLinkStates.set(linkKey, {
              state: 'all_complete',
              bundleId: transmission.bundle_id,
              timestamp: now,
            });
          } else if (isLastStation && !activeTransmissions.some((t) => t.bundle_id === transmission.bundle_id && t.to_station.toLowerCase() === 'iss')) {
            // Bundle at last ground station, waiting for ISS contact
            newLinkStates.set(linkKey, {
              state: 'waiting_iss',
              bundleId: transmission.bundle_id,
              timestamp: now,
            });
          } else {
            // Transmitting to ISS
            newLinkStates.set(linkKey, {
              state: 'transmitting_iss',
              bundleId: transmission.bundle_id,
              timestamp: now,
            });
          }
        } else if (isIssLink) {
          // ISS link but route not fully established yet
          newLinkStates.set(linkKey, {
            state: 'transmitting_iss',
            bundleId: transmission.bundle_id,
            timestamp: now,
          });
        } else {
          // Regular ground-to-ground transmission
          newLinkStates.set(linkKey, {
            state: 'transmitting',
            bundleId: transmission.bundle_id,
            timestamp: now,
          });
        }
      } else {
        // No bundle info, use default transmission state
        newLinkStates.set(linkKey, {
          state: isIssLink ? 'transmitting_iss' : 'transmitting',
          bundleId: transmission.bundle_id,
          timestamp: now,
        });
      }
    });

    // Handle completed transmissions - mark as green and find next link in route
    newCompleted.forEach((bundleId) => {
      // Find the completed link
      previousLinkStatesRef.current.forEach((state, linkKey) => {
        if (state.bundleId === bundleId && (state.state === 'transmitting' || state.state === 'transmitting_iss')) {
          // Find bundle to get route
          const bundle = Object.values(dtnQueues)
            .flat()
            .find((b) => b.bundle_id === bundleId);

          if (bundle) {
            const route = bundle.route || bundle.hops || [];
            const currentCustodian = bundle.current_custodian?.toLowerCase();
            const currentIndex = route.findIndex((r) => r.toLowerCase() === currentCustodian);

            // Check if this is the last ground station before ISS
            const isLastStation = currentIndex >= 0 && currentIndex === route.length - 2;

            if (isLastStation) {
              // Bundle reached last ground station - reset all previous links for this bundle
              // and only show the ISS link
              previousLinkStatesRef.current.forEach((prevState, prevLinkKey) => {
                if (prevState.bundleId === bundleId && prevLinkKey !== linkKey) {
                  // Reset previous links (don't add them to newLinkStates)
                  // They will return to default state
                }
              });

              // Mark completed link as green (briefly)
              newLinkStates.set(linkKey, {
                state: 'completed',
                bundleId,
                timestamp: now,
              });

              // Set ISS link to waiting state
              const issLinkKey = `${currentCustodian}-iss`;
              newLinkStates.set(issLinkKey, {
                state: 'waiting_iss',
                bundleId,
                timestamp: now,
              });
            } else {
              // Regular completion - mark as green and highlight next link
              newLinkStates.set(linkKey, {
                state: 'completed',
                bundleId,
                timestamp: now,
              });

              // Find next hop in route
              if (currentIndex >= 0 && currentIndex < route.length - 1) {
                const nextHop = route[currentIndex + 1]?.toLowerCase();
                const nextLinkKey = `${currentCustodian}-${nextHop}`;

                // Check if there's an active transmission for this bundle on the next link
                const nextTransmission = activeTransmissions.find(
                  (t) =>
                    t.bundle_id === bundleId &&
                    t.from_station.toLowerCase() === currentCustodian &&
                    t.to_station.toLowerCase() === nextHop
                );

                if (nextTransmission) {
                  // Next link is already active, it will be handled above
                } else if (nextHop === 'iss') {
                  // Next hop is ISS - check if bundle is at last ground station
                  const isNextLastStation = currentIndex === route.length - 2;
                  if (isNextLastStation) {
                    newLinkStates.set(nextLinkKey, {
                      state: 'waiting_iss',
                      bundleId,
                      timestamp: now,
                    });
                  }
                }
              }
            }
          } else {
            // No bundle info - just mark as completed
            newLinkStates.set(linkKey, {
              state: 'completed',
              bundleId,
              timestamp: now,
            });
          }
        }
      });
    });

    // Check for bundles at last ground station waiting for ISS or delivered
    Object.values(dtnQueues).forEach((queue) => {
      queue.forEach((bundle) => {
        const route = bundle.route || bundle.hops || [];
        if (route.length >= 2 && route[route.length - 1]?.toLowerCase() === 'iss') {
          const lastGroundStation = route[route.length - 2]?.toLowerCase();
          const currentCustodian = bundle.current_custodian?.toLowerCase();
          const linkKey = `${lastGroundStation}-iss`;

          if (bundle.status === 'DELIVERED') {
            // Bundle delivered to ISS - mark as all complete
            if (!newLinkStates.has(linkKey)) {
              newLinkStates.set(linkKey, {
                state: 'all_complete',
                bundleId: bundle.bundle_id,
                timestamp: now,
              });
            }
          } else if (
            currentCustodian === lastGroundStation &&
            !activeTransmissions.some((t) => t.bundle_id === bundle.bundle_id)
          ) {
            // Bundle is at last ground station and not actively transmitting - waiting for ISS
            if (!newLinkStates.has(linkKey)) {
              newLinkStates.set(linkKey, {
                state: 'waiting_iss',
                bundleId: bundle.bundle_id,
                timestamp: now,
              });
            }
          }
        }
      });
    });

    // Clean up old completed states after 2 seconds
    previousLinkStatesRef.current.forEach((state, linkKey) => {
      const age = now - state.timestamp;
      if ((state.state === 'completed' || state.state === 'all_complete') && age > 2000) {
        // Remove after 2 seconds - don't add to newLinkStates
        return;
      }

      // Keep other states if not overwritten
      if (!newLinkStates.has(linkKey) && state.state !== 'completed' && state.state !== 'all_complete') {
        newLinkStates.set(linkKey, state);
      }
    });

    setLinkStates(newLinkStates);
    previousLinkStatesRef.current = newLinkStates;
    previousTransmissionsRef.current = currentTransmissionIds;
  }, [activeTransmissions, dtnQueues]);

  // Get link color based on state
  const getLinkColor = (linkKey: string): string => {
    const state = linkStates.get(linkKey);
    if (!state) return '#6b7280'; // Default gray

    switch (state.state) {
      case 'transmitting':
      case 'transmitting_iss':
        return '#f97316'; // Orange
      case 'completed':
      case 'all_complete':
        return '#22c55e'; // Green
      case 'waiting_iss':
        return blinkState ? '#f97316' : 'transparent'; // Blinking orange
      default:
        return '#6b7280'; // Default gray
    }
  };

  // Get link width based on state
  const getLinkWidth = (linkKey: string): number => {
    const state = linkStates.get(linkKey);
    if (!state) return 1;

    switch (state.state) {
      case 'transmitting':
      case 'transmitting_iss':
      case 'completed':
      case 'all_complete':
      case 'waiting_iss':
        return 3;
      default:
        return 1;
    }
  };

  // Get node color (highlight if part of active transmission)
  const getNodeColor = (nodeId: string): string => {
    if (nodeId === 'iss') {
      return '#3b82f6'; // Blue for ISS
    }

    // Check if node is part of active transmission
    const isActive = activeTransmissions.some(
      (t) => t.from_station.toLowerCase() === nodeId || t.to_station.toLowerCase() === nodeId
    );

    if (isActive) {
      return '#f97316'; // Orange when transmitting
    }

    const station = stations.find((s) => s.id === nodeId);
    return station?.color || '#6b7280';
  };

  // Get node size
  const getNodeSize = (nodeId: string): number => {
    if (nodeId === 'iss') return 20;
    const isActive = activeTransmissions.some(
      (t) => t.from_station.toLowerCase() === nodeId || t.to_station.toLowerCase() === nodeId
    );
    return isActive ? 12 : 10;
  };

  // Render edges (links)
  const renderEdges = () => {
    const edges: JSX.Element[] = [];

    // Render mesh connections
    meshConnections.forEach((conn) => {
      const fromPos = nodePositions.get(conn.from.toLowerCase());
      const toPos = nodePositions.get(conn.to.toLowerCase());
      if (!fromPos || !toPos) return;

      const linkKey = `${conn.from.toLowerCase()}-${conn.to.toLowerCase()}`;
      const color = getLinkColor(linkKey);
      const width = getLinkWidth(linkKey);

      edges.push(
        <line
          key={linkKey}
          x1={fromPos.x}
          y1={fromPos.y}
          x2={toPos.x}
          y2={toPos.y}
          stroke={color}
          strokeWidth={width}
          opacity={color === 'transparent' ? 0 : 0.6}
        />
      );
    });

    // Render ISS links (from active station to ISS)
    if (activeStationId) {
      const stationPos = nodePositions.get(activeStationId.toLowerCase());
      const issPos = nodePositions.get('iss');
      if (stationPos && issPos) {
        const linkKey = `${activeStationId.toLowerCase()}-iss`;
        const color = getLinkColor(linkKey);
        const width = getLinkWidth(linkKey);

        edges.push(
          <line
            key={linkKey}
            x1={stationPos.x}
            y1={stationPos.y}
            x2={issPos.x}
            y2={issPos.y}
            stroke={color}
            strokeWidth={width}
            opacity={color === 'transparent' ? 0 : 0.6}
          />
        );
      }
    }

    // Also render ISS links from active transmissions
    activeTransmissions.forEach((transmission) => {
      const from = transmission.from_station.toLowerCase();
      const to = transmission.to_station.toLowerCase();
      if (to === 'iss' || from === 'iss') {
        const fromPos = nodePositions.get(from);
        const toPos = nodePositions.get(to === 'iss' ? 'iss' : from);
        const issPos = nodePositions.get('iss');
        const otherPos = to === 'iss' ? fromPos : toPos;

        if (fromPos && issPos && otherPos) {
          const linkKey = `${from}-iss`;
          const color = getLinkColor(linkKey);
          const width = getLinkWidth(linkKey);

          // Check if this edge already exists
          const exists = edges.some((edge) => edge.key === linkKey);
          if (!exists) {
            edges.push(
              <line
                key={linkKey}
                x1={otherPos.x}
                y1={otherPos.y}
                x2={issPos.x}
                y2={issPos.y}
                stroke={color}
                strokeWidth={width}
                opacity={color === 'transparent' ? 0 : 0.6}
              />
            );
          }
        }
      }
    });

    return edges;
  };

  // Render nodes
  const renderNodes = () => {
    const nodes: JSX.Element[] = [];

    // Render ISS node
    const issPos = nodePositions.get('iss');
    if (issPos) {
      const color = getNodeColor('iss');
      const size = getNodeSize('iss');
      nodes.push(
        <g key="iss">
          <circle cx={issPos.x} cy={issPos.y} r={size} fill={color} stroke="#fff" strokeWidth={2} />
          <text
            x={issPos.x}
            y={issPos.y + size + 12}
            textAnchor="middle"
            className="text-[10px] fill-foreground font-semibold"
          >
            ISS
          </text>
        </g>
      );
    }

    // Render station nodes
    stations.forEach((station) => {
      const pos = nodePositions.get(station.id);
      if (!pos) return;

      const color = getNodeColor(station.id);
      const size = getNodeSize(station.id);

      nodes.push(
        <g key={station.id}>
          <circle cx={pos.x} cy={pos.y} r={size} fill={color} stroke="#fff" strokeWidth={1.5} />
          <text
            x={pos.x}
            y={pos.y + size + 10}
            textAnchor="middle"
            className="text-[9px] fill-foreground font-medium"
          >
            {station.name.substring(0, 4)}
          </text>
        </g>
      );
    });

    return nodes;
  };

  return (
    <Card className="p-4">
      <div className="mb-3">
        <h3 className="text-xs font-semibold tracking-wider uppercase text-secondary">NETWORK TOPOLOGY</h3>
        <p className="text-[10px] text-secondary/60 mt-1">Mininet Network Graph</p>
      </div>

      <div className="w-full flex justify-center">
        <svg width="400" height="400" viewBox="0 0 400 400" className="border border-border rounded">
          <defs>
            <filter id="glow">
              <feGaussianBlur stdDeviation="3" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          {renderEdges()}
          {renderNodes()}
        </svg>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-[9px] text-secondary/80">
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-orange-500" />
          <span>Transmitting</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-green-500" />
          <span>Completed</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-gray-500" />
          <span>Idle</span>
        </div>
      </div>
    </Card>
  );
};

export default NetworkTopology;

