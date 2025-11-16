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

    // Process all bundles to track their routes
    const allBundles = Object.values(dtnQueues).flat();
    
    // Track bundles that reached last ground station - need to reset their previous links
    const bundlesAtLastStation = new Set<string>();
    const bundlesAtLastStationLinks = new Map<string, string>(); // bundleId -> issLinkKey

    allBundles.forEach((bundle) => {
      const route = bundle.route || bundle.hops || [];
      if (route.length < 2) return;

      const currentCustodian = bundle.current_custodian?.toLowerCase();
      const currentIndex = route.findIndex((r) => r.toLowerCase() === currentCustodian);
      const isLastStation = currentIndex >= 0 && currentIndex === route.length - 2;
      const isDelivered = bundle.status === 'DELIVERED';

      // Only mark as last station if bundle is actually AT the last ground station
      if (isLastStation && !isDelivered && currentCustodian === route[route.length - 2]?.toLowerCase()) {
        bundlesAtLastStation.add(bundle.bundle_id);
        const lastGroundStation = route[route.length - 2]?.toLowerCase();
        const issLinkKey = `${lastGroundStation}-iss`;
        bundlesAtLastStationLinks.set(bundle.bundle_id, issLinkKey);
      }
    });

    // Check if ISS is in contact (activeStationId is set)
    const issInContact = activeStationId !== null && activeStationId !== undefined;
    const stationWithIssContact = issInContact ? activeStationId.toLowerCase() : null;

    // Check if all bundles are done transmitting at the station with ISS contact
    const stationWithContactQueues = stationWithIssContact ? dtnQueues[stationWithIssContact] || [] : [];
    const hasPendingBundlesAtContactStation = stationWithContactQueues.some(
      (b) => b.status !== 'DELIVERED' && b.status !== 'EXPIRED'
    );
    const hasActiveTransmissionsAtContactStation = activeTransmissions.some(
      (t) => t.from_station.toLowerCase() === stationWithIssContact && t.to_station.toLowerCase() === 'iss'
    );

    // Process bundles - prioritize last station bundles
    allBundles.forEach((bundle) => {
      const route = bundle.route || bundle.hops || [];
      if (route.length < 2) return;

      const currentCustodian = bundle.current_custodian?.toLowerCase();
      const currentIndex = route.findIndex((r) => r.toLowerCase() === currentCustodian);
      const isLastStation = bundlesAtLastStation.has(bundle.bundle_id);
      const isDelivered = bundle.status === 'DELIVERED';

      // Find active transmission for this bundle
      const activeTransmission = activeTransmissions.find((t) => t.bundle_id === bundle.bundle_id);

      if (isLastStation && !isDelivered) {
        // Bundle at last ground station - ONLY show ISS link, reset all previous links
        const lastGroundStation = route[route.length - 2]?.toLowerCase();
        if (currentCustodian !== lastGroundStation) {
          // Bundle is not yet at the last station, skip
          return;
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
          // Currently transmitting to ISS - always solid orange
          newLinkStates.set(issLinkKey, {
            state: 'transmitting_iss',
            bundleId: bundle.bundle_id,
            timestamp: now,
          });
        } else if (isStationWithIssContact) {
          // ISS is in contact with this station
          // If there are pending bundles or active transmissions, show solid orange
          // Otherwise, if all bundles are done, show green for 2 seconds
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
            // Still have bundles to transmit - solid orange (will be set by active transmission)
            // Don't set waiting_iss here
          } else {
            // All bundles done - check if we should show green
            const prevState = previousLinkStatesRef.current.get(issLinkKey);
            if (prevState && (prevState.state === 'transmitting_iss' || prevState.state === 'waiting_iss')) {
              // Just finished - show green for 2 seconds
              newLinkStates.set(issLinkKey, {
                state: 'all_complete',
                bundleId: bundle.bundle_id,
                timestamp: now,
              });
            }
          }
        } else {
          // ISS NOT in contact with this station - blink while waiting
          newLinkStates.set(issLinkKey, {
            state: 'waiting_iss',
            bundleId: bundle.bundle_id,
            timestamp: now,
          });
        }
      } else if (isDelivered) {
        // Bundle delivered - mark ISS link as complete
        if (route.length >= 2) {
          const lastGroundStation = route[route.length - 2]?.toLowerCase();
          const issLinkKey = `${lastGroundStation}-iss`;
          newLinkStates.set(issLinkKey, {
            state: 'all_complete',
            bundleId: bundle.bundle_id,
            timestamp: now,
          });
        }
      } else if (activeTransmission && !bundlesAtLastStation.has(bundle.bundle_id)) {
        // Active transmission - highlight current link and all previous links in route
        const from = activeTransmission.from_station.toLowerCase();
        const to = activeTransmission.to_station.toLowerCase();
        const currentLinkKey = `${from}-${to}`;
        const isIssLink = to === 'iss' || from === 'iss';

        // Highlight current transmitting link
        // If transmitting to ISS and ISS is in contact, use solid orange (transmitting_iss)
        // Otherwise use regular transmitting state
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

        // Highlight all previous links in the route as completed (green)
        if (currentIndex > 0) {
          for (let i = 0; i < currentIndex; i++) {
            const prevFrom = route[i]?.toLowerCase();
            const prevTo = route[i + 1]?.toLowerCase();
            if (prevFrom && prevTo) {
              const prevLinkKey = `${prevFrom}-${prevTo}`;
              // Don't override if this is an ISS link for a bundle at last station
              if (prevLinkKey.includes('-iss') && bundlesAtLastStation.has(bundle.bundle_id)) {
                continue;
              }
              const existingState = newLinkStates.get(prevLinkKey);
              // Only mark as completed if not already marked as transmitting or waiting
              if (!existingState || existingState.state === 'completed' || existingState.state === 'all_complete') {
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
        // Bundle is queued but has a route - highlight completed links
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

    // Process active transmissions (for bundles not yet in queues or to override states)
    activeTransmissions.forEach((transmission) => {
      const from = transmission.from_station.toLowerCase();
      const to = transmission.to_station.toLowerCase();
      const linkKey = `${from}-${to}`;
      const isIssLink = to === 'iss' || from === 'iss';

      // Get bundle to check route and status
      const bundle = allBundles.find((b) => b.bundle_id === transmission.bundle_id);

      // If this is an ISS link and bundle is at last station, ensure it's set to transmitting_iss
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

        // Highlight current link (override if needed)
        // Skip if this is an ISS link for bundle at last station (already handled above)
        if (!(isIssLink && bundlesAtLastStation.has(transmission.bundle_id))) {
          const existingState = newLinkStates.get(linkKey);
          if (!existingState || existingState.state === 'completed' || existingState.state === 'all_complete') {
            newLinkStates.set(linkKey, {
              state: isIssLink ? 'transmitting_iss' : 'transmitting',
              bundleId: transmission.bundle_id,
              timestamp: now,
            });
          }
        }

        // Highlight previous links in route as completed
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
              if (!prevExistingState || prevExistingState.state === 'completed' || prevExistingState.state === 'all_complete') {
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
        // Skip if this is an ISS link for bundle at last station
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

    // Handle completed transmissions - mark completed link as green
    newCompleted.forEach((bundleId) => {
      // Find the completed link from previous state
      previousLinkStatesRef.current.forEach((state, linkKey) => {
        if (state.bundleId === bundleId && (state.state === 'transmitting' || state.state === 'transmitting_iss')) {
          // Mark as completed (green)
          newLinkStates.set(linkKey, {
            state: 'completed',
            bundleId,
            timestamp: now,
          });
        }
      });
    });

    // Reset previous links for bundles that reached last ground station
    bundlesAtLastStation.forEach((bundleId) => {
      const issLinkKey = bundlesAtLastStationLinks.get(bundleId);
      previousLinkStatesRef.current.forEach((prevState, prevLinkKey) => {
        // Remove all previous link states for this bundle (except ISS link which is already set above)
        if (prevState.bundleId === bundleId && prevLinkKey !== issLinkKey) {
          // Don't add to newLinkStates - this resets the link to default
        }
      });
    });

    stations.forEach((station) => {
      const stationIssLinkKey = `${station.id.toLowerCase()}-iss`;
      const linkState = newLinkStates.get(stationIssLinkKey);
      
      // If this ISS link has waiting_iss state, verify it's correct
      if (linkState && linkState.state === 'waiting_iss') {
        // Check if this station is actually the last ground station for this bundle
        const bundle = allBundles.find((b) => b.bundle_id === linkState.bundleId);
        if (bundle) {
          const route = bundle.route || bundle.hops || [];
          const lastGroundStation = route.length >= 2 ? route[route.length - 2]?.toLowerCase() : null;
          const currentCustodian = bundle.current_custodian?.toLowerCase();
          
          // Only keep waiting_iss if this is the correct last station AND bundle is at that station
          if (lastGroundStation !== station.id.toLowerCase() || currentCustodian !== lastGroundStation) {
            // Wrong station - remove waiting_iss state
            newLinkStates.delete(stationIssLinkKey);
          }
        } else {
          // Bundle not found - remove waiting_iss state
          newLinkStates.delete(stationIssLinkKey);
        }
      }
    });

    // Clean up old completed states after 2 seconds
    previousLinkStatesRef.current.forEach((state, linkKey) => {
      const age = now - state.timestamp;
      
      // Skip if this is a bundle at last station (already handled above)
      if (bundlesAtLastStation.has(state.bundleId) && !linkKey.includes('-iss')) {
        return;
      }
      
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
  }, [activeTransmissions, dtnQueues, activeStationId]);

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
        return '#f97316'; // Always orange for waiting_iss (blinking handled by opacity)
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

    // Render ISS links from ALL stations - always visible
    const issPos = nodePositions.get('iss');
    if (issPos) {
      stations.forEach((station) => {
        const stationPos = nodePositions.get(station.id);
        if (!stationPos) return;

        const linkKey = `${station.id.toLowerCase()}-iss`;
        const state = linkStates.get(linkKey);
        const color = getLinkColor(linkKey);
        const width = getLinkWidth(linkKey);
        
        // Always show ISS links - higher opacity for active states, visible for idle
        let opacity = 0.6;
        if (state) {
          if (state.state === 'waiting_iss') {
            // Blinking - use blinkState to control opacity
            opacity = blinkState ? 0.9 : 0.6;
          } else if (state.state === 'transmitting_iss' || state.state === 'transmitting' || 
                     state.state === 'completed' || state.state === 'all_complete') {
            opacity = 0.7; // Active states
          } else {
            opacity = 0.6; // Default
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

