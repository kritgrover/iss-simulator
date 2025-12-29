import { useEffect, useState, useRef, useMemo } from 'react';
import { Card } from '@/components/ui/card';
import { DTNBundle } from '@/types/dtnBundle';
import { GroundStation } from '@/types/groundStation';
import { InfoTooltip } from '@/components/ui/info-tooltip';

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

  // Calculate node positions
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

    previousTransmissionsRef.current.forEach((id) => {
      if (!currentTransmissionIds.has(id)) {
        newCompleted.add(id);
      }
    });

    // Update link states based on active transmissions
    const newLinkStates = new Map<string, LinkStateData>();
    const now = Date.now();

    // Process all bundles to track their routes
    const allBundles = Object.values(dtnQueues).flat();
    
    // Helper function to get the last ground station from a route
    const getLastGroundStation = (route: string[]): string | null => {
      if (route.length < 1) return null;
      const lastElement = route[route.length - 1]?.toLowerCase();
      if (lastElement === 'iss') {
        return route.length >= 2 ? route[route.length - 2]?.toLowerCase() || null : null;
      } else {
        return route[route.length - 1]?.toLowerCase() || null;
      }
    };
    
    // Track bundles that reached last ground station
    const bundlesAtLastStation = new Set<string>();
    const bundlesAtLastStationLinks = new Map<string, string>(); // bundleId -> issLinkKey

    allBundles.forEach((bundle) => {
      const route = bundle.route || bundle.hops || [];
      if (route.length < 1) return;

      const currentCustodian = bundle.current_custodian?.toLowerCase();
      const lastGroundStation = getLastGroundStation(route);
      
      if (!lastGroundStation) return;
      
      const isLastStation = currentCustodian === lastGroundStation;
      const isDelivered = bundle.status === 'DELIVERED';

      if (isLastStation && !isDelivered) {
        const stationQueue = dtnQueues[lastGroundStation] || [];
        const bundleInQueue = stationQueue.some(b => b.bundle_id === bundle.bundle_id);
        
        if (bundleInQueue) {
          bundlesAtLastStation.add(bundle.bundle_id);
          const issLinkKey = `${lastGroundStation}-iss`;
          bundlesAtLastStationLinks.set(bundle.bundle_id, issLinkKey);
        }
      }
    });

    // Check if ISS is in contact
    const issInContact = activeStationId !== null && activeStationId !== undefined;
    const stationWithIssContact = issInContact ? activeStationId.toLowerCase() : null;

    const stationWithContactQueues = stationWithIssContact ? dtnQueues[stationWithIssContact] || [] : [];
    const hasPendingBundlesAtContactStation = stationWithContactQueues.some(
      (b) => b.status !== 'DELIVERED' && b.status !== 'EXPIRED'
    );
    const hasActiveTransmissionsAtContactStation = activeTransmissions.some(
      (t) => t.from_station.toLowerCase() === stationWithIssContact && t.to_station.toLowerCase() === 'iss'
    );

    // Process bundles
    allBundles.forEach((bundle) => {
      const route = bundle.route || bundle.hops || [];
      if (route.length < 2) return;

      const currentCustodian = bundle.current_custodian?.toLowerCase();
      const currentIndex = route.findIndex((r) => r.toLowerCase() === currentCustodian);
      const isLastStation = bundlesAtLastStation.has(bundle.bundle_id);
      const isDelivered = bundle.status === 'DELIVERED';

      const activeTransmission = activeTransmissions.find((t) => t.bundle_id === bundle.bundle_id);

      if (isLastStation && !isDelivered) {
        // Bundle at last ground station
        const lastGroundStation = getLastGroundStation(route);
        if (!lastGroundStation || currentCustodian !== lastGroundStation) {
          // Bundle is not yet at the last station, skip
          return;
        }
        
        // ensure the bundle is actually queued at this station
        const stationQueue = dtnQueues[lastGroundStation] || [];
        const bundleInQueue = stationQueue.some(b => b.bundle_id === bundle.bundle_id);
        if (!bundleInQueue) {
          // Bundle not in this station's queue, skip
          return;
        }

        // Mark all previous links in the route as completed
        if (currentIndex > 0) {
          // Mark all links from start up to and including the link TO the last ground station
          for (let i = 0; i < currentIndex; i++) {
            const prevFrom = route[i]?.toLowerCase();
            const prevTo = route[i + 1]?.toLowerCase();
            if (prevFrom && prevTo) {
              const prevLinkKey = `${prevFrom}-${prevTo}`;
              // Don't mark ISS links as completed here
              if (!prevLinkKey.includes('-iss')) {
                const existingState = newLinkStates.get(prevLinkKey);
                // allow overriding transmitting state for bundles at last station
                if (!existingState || existingState.state !== 'waiting_iss') {
                  newLinkStates.set(prevLinkKey, {
                    state: 'completed',
                    bundleId: bundle.bundle_id,
                    timestamp: now,
                  });
                }
              }
            }
          }
        }

        const issLinkKey = bundlesAtLastStationLinks.get(bundle.bundle_id);
        if (!issLinkKey) {
          // Should not happen, but skip if no ISS link key
          return;
        }

        // Check if this last station is the one currently in contact with ISS
        const isStationWithIssContact = issInContact && lastGroundStation === stationWithIssContact;

        if (activeTransmission && activeTransmission.to_station.toLowerCase() === 'iss' && 
            activeTransmission.from_station.toLowerCase() === currentCustodian) {
          // Currently transmitting to ISS
          newLinkStates.set(issLinkKey, {
            state: 'transmitting_iss',
            bundleId: bundle.bundle_id,
            timestamp: now,
          });
        } else if (isStationWithIssContact) {
          // ISS is in contact with this station
          const stationBundles = dtnQueues[lastGroundStation] || [];
          const hasPendingBundles = stationBundles.some(
            (b) => b.status !== 'DELIVERED' && b.status !== 'EXPIRED' && b.bundle_id !== bundle.bundle_id
          );
          const hasActiveTx = activeTransmissions.some(
            (t) => t.from_station.toLowerCase() === lastGroundStation && 
                   t.to_station.toLowerCase() === 'iss' &&
                   t.bundle_id !== bundle.bundle_id
          );

          if (hasPendingBundles || hasActiveTx) {
            // Still have bundles to transmit
            // Don't set waiting_iss here
          } else {
            // All bundles done
            const prevState = previousLinkStatesRef.current.get(issLinkKey);
            if (prevState && (prevState.state === 'transmitting_iss' || prevState.state === 'waiting_iss')) {
              // Just finished
              newLinkStates.set(issLinkKey, {
                state: 'all_complete',
                bundleId: bundle.bundle_id,
                timestamp: now,
              });
            }
          }
        } else {
          // ISS NOT in contact with this station
          newLinkStates.set(issLinkKey, {
            state: 'waiting_iss',
            bundleId: bundle.bundle_id,
            timestamp: now,
          });
        }
      } else if (isDelivered) {
        // Bundle delivered
        const lastGroundStation = getLastGroundStation(route);
        if (lastGroundStation) {
          const issLinkKey = `${lastGroundStation}-iss`;
          newLinkStates.set(issLinkKey, {
            state: 'all_complete',
            bundleId: bundle.bundle_id,
            timestamp: now,
          });
        }
      } else if (activeTransmission && !bundlesAtLastStation.has(bundle.bundle_id)) {
        // Active transmission
        const from = activeTransmission.from_station.toLowerCase();
        const to = activeTransmission.to_station.toLowerCase();
        const currentLinkKey = `${from}-${to}`;
        const isIssLink = to === 'iss' || from === 'iss';

        // Highlight current transmitting link
        if (isIssLink) {
          newLinkStates.set(currentLinkKey, {
            state: 'transmitting_iss',
            bundleId: bundle.bundle_id,
            timestamp: now,
          });
        } else {
          newLinkStates.set(currentLinkKey, {
            state: 'transmitting',
            bundleId: bundle.bundle_id,
            timestamp: now,
          });
        }

        // Highlight all previous links in the route as completed
        if (currentIndex > 0) {
          for (let i = 0; i < currentIndex; i++) {
            const prevFrom = route[i]?.toLowerCase();
            const prevTo = route[i + 1]?.toLowerCase();
            if (prevFrom && prevTo) {
              const prevLinkKey = `${prevFrom}-${prevTo}`;
              if (prevLinkKey.includes('-iss') && bundlesAtLastStation.has(bundle.bundle_id)) {
                continue;
              }
              const existingState = newLinkStates.get(prevLinkKey);
              // Only mark as completed if not a waiting_iss state
              if (!existingState || existingState.state !== 'waiting_iss') {
                newLinkStates.set(prevLinkKey, {
                  state: 'completed',
                  bundleId: bundle.bundle_id,
                  timestamp: now,
                });
              }
            }
          }
        }
      } else if (currentIndex > 0 && !bundlesAtLastStation.has(bundle.bundle_id)) {
        // Bundle is queued but has a route
        for (let i = 0; i < currentIndex; i++) {
          const prevFrom = route[i]?.toLowerCase();
          const prevTo = route[i + 1]?.toLowerCase();
          if (prevFrom && prevTo) {
            const prevLinkKey = `${prevFrom}-${prevTo}`;
            // Don't override if this is an ISS link for a bundle at last station
            if (prevLinkKey.includes('-iss') && bundlesAtLastStation.has(bundle.bundle_id)) {
              continue;
            }
            newLinkStates.set(prevLinkKey, {
              state: 'completed',
              bundleId: bundle.bundle_id,
              timestamp: now,
            });
          }
        }
      }
    });

    // Process active transmissions
    activeTransmissions.forEach((transmission) => {
      const from = transmission.from_station.toLowerCase();
      const to = transmission.to_station.toLowerCase();
      const linkKey = `${from}-${to}`;
      const isIssLink = to === 'iss' || from === 'iss';

      // Get bundle to check route and status
      const bundle = allBundles.find((b) => b.bundle_id === transmission.bundle_id);

      // If this is an ISS link and bundle is at last station
      if (isIssLink && bundlesAtLastStation.has(transmission.bundle_id)) {
        const issLinkKey = bundlesAtLastStationLinks.get(transmission.bundle_id);
        if (issLinkKey) {
          // Always show solid orange when actively transmitting to ISS
          newLinkStates.set(issLinkKey, {
            state: 'transmitting_iss',
            bundleId: transmission.bundle_id,
            timestamp: now,
          });
        }
        // Continue to process route highlighting below
      }

      if (bundle) {
        const route = bundle.route || bundle.hops || [];
        const currentCustodian = bundle.current_custodian?.toLowerCase();
        const currentIndex = route.findIndex((r) => r.toLowerCase() === currentCustodian);

        // Highlight current link
        if (!(isIssLink && bundlesAtLastStation.has(transmission.bundle_id))) {
          const existingState = newLinkStates.get(linkKey);
          if (!existingState || (existingState.bundleId === transmission.bundle_id && 
              existingState.state !== 'completed' && existingState.state !== 'all_complete')) {
            newLinkStates.set(linkKey, {
              state: isIssLink ? 'transmitting_iss' : 'transmitting',
              bundleId: transmission.bundle_id,
              timestamp: now,
            });
          }
        }

        // Highlight previous links in route
        if (currentIndex > 0) {
          for (let i = 0; i < currentIndex; i++) {
            const prevFrom = route[i]?.toLowerCase();
            const prevTo = route[i + 1]?.toLowerCase();
            if (prevFrom && prevTo) {
              const prevLinkKey = `${prevFrom}-${prevTo}`;
              // Don't override ISS links for bundles at last station
              if (prevLinkKey.includes('-iss') && bundlesAtLastStation.has(transmission.bundle_id)) {
                continue;
              }
              const prevExistingState = newLinkStates.get(prevLinkKey);
              // Only mark as completed if not a waiting_iss state
              if (!prevExistingState || prevExistingState.state !== 'waiting_iss') {
                newLinkStates.set(prevLinkKey, {
                  state: 'completed',
                  bundleId: transmission.bundle_id,
                  timestamp: now,
                });
              }
            }
          }
        }
      } else {
        // No bundle info, use default transmission state
        if (!(isIssLink && bundlesAtLastStation.has(transmission.bundle_id))) {
          if (!newLinkStates.has(linkKey)) {
            newLinkStates.set(linkKey, {
              state: isIssLink ? 'transmitting_iss' : 'transmitting',
              bundleId: transmission.bundle_id,
              timestamp: now,
            });
          }
        }
      }
    });

    // Handle completed transmissions
    newCompleted.forEach((bundleId) => {
      previousLinkStatesRef.current.forEach((state, linkKey) => {
        if (state.bundleId === bundleId && (state.state === 'transmitting' || state.state === 'transmitting_iss')) {
          // Mark as completed
          newLinkStates.set(linkKey, {
            state: 'completed',
            bundleId,
            timestamp: now,
          });
        }
      });
    });

    // Reset previous links
    bundlesAtLastStation.forEach((bundleId) => {
      const issLinkKey = bundlesAtLastStationLinks.get(bundleId);
      previousLinkStatesRef.current.forEach((prevState, prevLinkKey) => {
        // Remove all previous link states for this bundle
        if (prevState.bundleId === bundleId && prevLinkKey !== issLinkKey) {
          // Don't add to newLinkStates
        }
      });
    });

    stations.forEach((station) => {
      const stationIssLinkKey = `${station.id.toLowerCase()}-iss`;
      const linkState = newLinkStates.get(stationIssLinkKey);
      
      // If this ISS link has waiting_iss state
      if (linkState && linkState.state === 'waiting_iss') {
        // Check if this station is the last ground station for this bundle
        const bundle = allBundles.find((b) => b.bundle_id === linkState.bundleId);
        if (bundle) {
          const route = bundle.route || bundle.hops || [];
          const lastGroundStation = getLastGroundStation(route);
          const currentCustodian = bundle.current_custodian?.toLowerCase();
          
          // bundle must be at this station AND this station must be the last ground station
          const isCorrectStation = lastGroundStation === station.id.toLowerCase();
          const bundleAtStation = currentCustodian === station.id.toLowerCase();
          
          // bundle is actually in this station's queue
          const stationQueue = dtnQueues[station.id.toLowerCase()] || [];
          const bundleInQueue = stationQueue.some(b => b.bundle_id === linkState.bundleId);
          
          // Only keep waiting_iss if all conditions are met
          if (!isCorrectStation || !bundleAtStation || !bundleInQueue) {
            // remove waiting_iss state
            newLinkStates.delete(stationIssLinkKey);
          }
        } else {
          // remove waiting_iss state
          newLinkStates.delete(stationIssLinkKey);
        }
      }
    });

    // Clean up old completed states
    previousLinkStatesRef.current.forEach((state, linkKey) => {
      const age = now - state.timestamp;
      
      // Skip if this is a bundle at last station
      if (bundlesAtLastStation.has(state.bundleId) && !linkKey.includes('-iss')) {
        return;
      }
      
      if ((state.state === 'completed' || state.state === 'all_complete') && age > 2000) {
        // don't add to newLinkStates
        return;
      }

      // Keep other states
      if (!newLinkStates.has(linkKey) && state.state !== 'completed' && state.state !== 'all_complete') {
        newLinkStates.set(linkKey, state);
      }
    });

    setLinkStates(newLinkStates);
    previousLinkStatesRef.current = newLinkStates;
    previousTransmissionsRef.current = currentTransmissionIds;
  }, [activeTransmissions, dtnQueues, activeStationId]);

  // Get link color
  const getLinkColor = (linkKey: string): string => {
    let state = linkStates.get(linkKey);
    
    // If not found, try reverse direction
    if (!state) {
      const parts = linkKey.split('-');
      if (parts.length === 2) {
        const reverseKey = `${parts[1]}-${parts[0]}`;
        state = linkStates.get(reverseKey);
      }
    }

    if (!state) return '#6b7280';

    switch (state.state) {
      case 'transmitting':
      case 'transmitting_iss':
        return '#f97316';
      case 'completed':
      case 'all_complete':
        return '#22c55e';
      case 'waiting_iss':
        return '#f97316';
      default:
        return '#6b7280';
    }
  };

  // Get link width
  const getLinkWidth = (linkKey: string): number => {
    let state = linkStates.get(linkKey);

    // If not found, try reverse direction
    if (!state) {
      const parts = linkKey.split('-');
      if (parts.length === 2) {
        const reverseKey = `${parts[1]}-${parts[0]}`;
        state = linkStates.get(reverseKey);
      }
    }

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

  // Get node color
  const getNodeColor = (nodeId: string): string => {
    if (nodeId === 'iss') {
      return '#3b82f6';
    }

    // Check if node is part of active transmission
    const isActive = activeTransmissions.some(
      (t) => t.from_station.toLowerCase() === nodeId || t.to_station.toLowerCase() === nodeId
    );

    if (isActive) {
      return '#f97316';
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

  // Render edges
  const renderEdges = () => {
    const edges: JSX.Element[] = [];
    const renderedLinks = new Set<string>();

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
      renderedLinks.add(linkKey);
    });

    // Render ISS links
    const issPos = nodePositions.get('iss');
    if (issPos) {
      stations.forEach((station) => {
        const stationPos = nodePositions.get(station.id);
        if (!stationPos) return;

        const linkKey = `${station.id.toLowerCase()}-iss`;
        const state = linkStates.get(linkKey);
        const color = getLinkColor(linkKey);
        const width = getLinkWidth(linkKey);
        
        let opacity = 0.6;
        if (state) {
          if (state.state === 'waiting_iss') {
            opacity = blinkState ? 0.9 : 0.6;
          } else if (state.state === 'transmitting_iss' || state.state === 'transmitting' || 
                     state.state === 'completed' || state.state === 'all_complete') {
            opacity = 0.7;
          } else {
            opacity = 0.6;
          }
        }

        edges.push(
          <line
            key={linkKey}
            x1={stationPos.x}
            y1={stationPos.y}
            x2={issPos.x}
            y2={issPos.y}
            stroke={color}
            strokeWidth={width}
            opacity={opacity}
          />
        );
        renderedLinks.add(linkKey);
      });
    }

    return edges;
  };

  // Render stations
  const renderNodes = () => {
    const nodes: JSX.Element[] = [];

    // Render ISS
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
            className="text-[11px] fill-foreground font-semibold"
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
            className="text-[10px] fill-foreground font-medium"
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
        <div className="flex items-center gap-2">
          <h3 className="text-[13px] font-semibold tracking-wider uppercase text-secondary">NETWORK TOPOLOGY</h3>
          <InfoTooltip
            content={
              <div className="space-y-2">
                <div>
                  <strong>Network Topology</strong>
                </div>
                <div className="text-xs space-y-1.5">
                  <p>Visual representation of the DTN mesh network showing bundle routing and link states.</p>
                  <p><strong>Nodes:</strong></p>
                  <ul className="list-disc list-inside space-y-0.5 ml-2">
                    <li>Blue center: ISS</li>
                    <li>Colored circles: Ground stations (color = station identity)</li>
                    <li>Orange nodes: Currently transmitting</li>
                  </ul>
                  <p><strong>Link States:</strong></p>
                  <ul className="list-disc list-inside space-y-0.5 ml-2">
                    <li>Orange: Active transmission or waiting for ISS contact</li>
                    <li>Green: Completed transmission</li>
                    <li>Gray: Idle (no activity)</li>
                  </ul>
                  <p><strong>DTN Routing:</strong> Bundles are routed through the mesh network. Each station can forward bundles to other stations or directly to ISS when in contact.</p>
                  <p><strong>ISS Links:</strong> Dashed lines show potential ISS connections. Only active when station has line-of-sight.</p>
                  <p><strong>Understanding:</strong> The topology shows how bundles flow through the network. Orange links indicate active data transfer. Green shows completed paths.</p>
                </div>
              </div>
            }
          />
        </div>
        <p className="text-[11px] text-secondary/60 mt-1">Mininet Network Graph</p>
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

      <div className="mt-3 flex flex-wrap gap-2 text-[10px] text-secondary/80">
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

