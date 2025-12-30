import { useState, useMemo } from "react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BookOpen, Search } from "lucide-react";

interface ReferenceItem {
  id: string;
  title: string;
  category: "dtn" | "routing" | "link-budget" | "orbital";
  content: string;
  formula?: string;
  keywords: string[];
}

const referenceData: ReferenceItem[] = [
  // DTN Bundle Protocol
  {
    id: "dtn-1",
    title: "Bundle Protocol Overview",
    category: "dtn",
    content: "The Bundle Protocol (BP) is a network protocol designed to enable communication in challenged network environments where end-to-end connectivity cannot be guaranteed. It uses store-and-forward message switching with custody transfer.",
    keywords: ["bundle", "protocol", "store", "forward", "custody"],
  },
  {
    id: "dtn-2",
    title: "Bundle Structure",
    category: "dtn",
    content: "A bundle consists of: Primary Block (routing info), Payload Block (data), and optional Extension Blocks (metadata). Each bundle has a unique identifier and lifetime.",
    keywords: ["bundle", "structure", "primary", "payload", "block"],
  },
  {
    id: "dtn-3",
    title: "Custody Transfer",
    category: "dtn",
    content: "Custody transfer ensures reliable delivery by transferring responsibility for a bundle from one node to another. The receiving node acknowledges custody acceptance.",
    keywords: ["custody", "transfer", "reliable", "acknowledgment"],
  },
  {
    id: "dtn-4",
    title: "Bundle Lifetime",
    category: "dtn",
    content: "Each bundle has a lifetime (TTL) that prevents infinite storage. If a bundle expires before delivery, it is discarded. Lifetime is typically set based on expected network delays.",
    keywords: ["lifetime", "ttl", "expiration", "time"],
  },
  
  // Routing Algorithms
  {
    id: "routing-1",
    title: "Contact Graph Routing (CGR)",
    category: "routing",
    content: "CGR builds a contact graph from scheduled contacts between nodes. It computes the best path by considering contact start times, durations, and data volumes. CGR is deterministic and suitable for space networks with predictable contacts.",
    keywords: ["cgr", "contact", "graph", "routing", "scheduled"],
  },
  {
    id: "routing-2",
    title: "Epidemic Routing",
    category: "routing",
    content: "Epidemic routing floods bundles to all available contacts. Simple but bandwidth-intensive. Each node replicates bundles to every neighbor it encounters until delivery or expiration.",
    keywords: ["epidemic", "flooding", "replication", "simple"],
  },
  {
    id: "routing-3",
    title: "Spray and Wait",
    category: "routing",
    content: "Spray and Wait limits replication: first phase distributes L copies to L distinct nodes, second phase waits for one copy to reach destination. Balances delivery probability with resource usage.",
    keywords: ["spray", "wait", "replication", "limited"],
  },
  {
    id: "routing-4",
    title: "Prophet Routing",
    category: "routing",
    content: "PROPHET (Probabilistic Routing Protocol using History of Encounters and Transitivity) uses delivery predictability. Nodes with higher delivery probability to destination are preferred.",
    keywords: ["prophet", "probabilistic", "predictability", "history"],
  },
  
  // Link Budget Formulas
  {
    id: "link-1",
    title: "Free Space Path Loss",
    category: "link-budget",
    content: "Free space path loss (FSPL) calculates signal attenuation in vacuum. It increases with distance and frequency.",
    formula: "FSPL = 20 × log₁₀(d) + 20 × log₁₀(f) + 32.44\nwhere d = distance (km), f = frequency (MHz)",
    keywords: ["path", "loss", "free", "space", "attenuation"],
  },
  {
    id: "link-2",
    title: "Received Power",
    category: "link-budget",
    content: "Received power at the antenna depends on transmitted power, antenna gains, and path loss.",
    formula: "P_r = P_t + G_t + G_r - L_p\nwhere P_t = transmit power (dBm), G_t/r = antenna gains (dBi), L_p = path loss (dB)",
    keywords: ["received", "power", "transmit", "gain", "antenna"],
  },
  {
    id: "link-3",
    title: "Signal-to-Noise Ratio (SNR)",
    category: "link-budget",
    content: "SNR determines link quality. Higher SNR enables higher data rates and lower error rates.",
    formula: "SNR = P_r - N\nwhere P_r = received power (dBm), N = noise power (dBm)",
    keywords: ["snr", "signal", "noise", "ratio", "quality"],
  },
  {
    id: "link-4",
    title: "Link Margin",
    category: "link-budget",
    content: "Link margin is the difference between received SNR and required SNR. Positive margin ensures reliable communication.",
    formula: "Margin = SNR_received - SNR_required",
    keywords: ["margin", "reliability", "threshold", "required"],
  },
  
  // Orbital Mechanics
  {
    id: "orbital-1",
    title: "Kepler's Laws",
    category: "orbital",
    content: "Kepler's three laws describe planetary motion: 1) Orbits are elliptical with the primary at one focus, 2) Equal areas swept in equal times, 3) Period squared proportional to semi-major axis cubed.",
    keywords: ["kepler", "laws", "elliptical", "orbit", "period"],
  },
  {
    id: "orbital-2",
    title: "Two-Line Element (TLE)",
    category: "orbital",
    content: "TLE format encodes orbital elements: inclination, right ascension, eccentricity, argument of perigee, mean anomaly, and mean motion. Updated regularly for accurate predictions.",
    keywords: ["tle", "elements", "inclination", "eccentricity", "anomaly"],
  },
  {
    id: "orbital-3",
    title: "Orbital Period",
    category: "orbital",
    content: "Orbital period is the time for one complete orbit. For circular orbits, period depends only on semi-major axis and primary body mass.",
    formula: "T = 2π × √(a³ / μ)\nwhere a = semi-major axis, μ = gravitational parameter",
    keywords: ["period", "orbit", "time", "circular"],
  },
  {
    id: "orbital-4",
    title: "Ground Track",
    category: "orbital",
    content: "Ground track is the path a satellite traces on Earth's surface. It shifts westward each orbit due to Earth's rotation. ISS completes ~15.5 orbits per day.",
    keywords: ["ground", "track", "path", "rotation", "shift"],
  },
];

const EducationalPanel = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);

  const filteredReferences = useMemo(() => {
    if (!searchQuery.trim()) return referenceData;
    const query = searchQuery.toLowerCase();
    return referenceData.filter(
      (item) =>
        item.title.toLowerCase().includes(query) ||
        item.content.toLowerCase().includes(query) ||
        item.keywords.some((kw) => kw.toLowerCase().includes(query)) ||
        (item.formula && item.formula.toLowerCase().includes(query))
    );
  }, [searchQuery]);

  return (
    <Sheet open={isOpen} onOpenChange={setIsOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="sm" className="h-8">
          <BookOpen className="w-4 h-4 mr-2" />
          Learn
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-full sm:max-w-2xl flex flex-col p-0">
        <SheetHeader className="border-b p-6 pb-4 flex-shrink-0">
          <SheetTitle className="text-2xl">DTN & Space Communications Guide</SheetTitle>
          <SheetDescription className="mt-2">
            Learn about Delay-Tolerant Networking, bundle routing, link budgets, and orbital mechanics
          </SheetDescription>
        </SheetHeader>
        
        <ScrollArea className="flex-1 px-6">
          <div className="py-6">
            <Tabs defaultValue="overview" className="w-full">
              <TabsList className="grid w-full grid-cols-5 mb-6">
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="routing">Routing</TabsTrigger>
                <TabsTrigger value="link-budget">Link Budget</TabsTrigger>
                <TabsTrigger value="handoff">Handoff</TabsTrigger>
                <TabsTrigger value="protocol">Protocol Stack</TabsTrigger>
              </TabsList>

              {/* Overview Tab */}
              <TabsContent value="overview" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>What is DTN?</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      <strong>Delay-Tolerant Networking (DTN)</strong> is a networking architecture designed to operate in environments where continuous end-to-end connectivity cannot be guaranteed. Unlike traditional Internet protocols that assume immediate connectivity, DTN handles intermittent links, long delays, and high error rates.
                    </p>
                    <div className="space-y-2">
                      <h4 className="font-semibold text-sm">Key Characteristics:</h4>
                      <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground ml-4">
                        <li><strong>Store-and-Forward:</strong> Messages are stored at intermediate nodes until a path becomes available</li>
                        <li><strong>Asynchronous:</strong> No requirement for simultaneous sender and receiver connectivity</li>
                        <li><strong>Custody Transfer:</strong> Responsibility for delivery is transferred between nodes</li>
                        <li><strong>Bundle Protocol:</strong> Uses a standardized protocol for message encapsulation and routing</li>
                      </ul>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Why is DTN Needed?</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      Space communications face unique challenges that make traditional networking protocols impractical:
                    </p>
                    <div className="space-y-3">
                      <div>
                        <h4 className="font-semibold text-sm mb-1">Intermittent Connectivity</h4>
                        <p className="text-sm text-muted-foreground">
                          Satellites are only visible to ground stations for limited periods. The ISS, for example, has contact windows of 5-10 minutes per pass, with gaps of 45-90 minutes between passes.
                        </p>
                      </div>
                      <div>
                        <h4 className="font-semibold text-sm mb-1">Long Delays</h4>
                        <p className="text-sm text-muted-foreground">
                          Signal propagation delays can be significant (up to 1.3 seconds for geostationary satellites). Deep space missions face delays of minutes to hours.
                        </p>
                      </div>
                      <div>
                        <h4 className="font-semibold text-sm mb-1">High Error Rates</h4>
                        <p className="text-sm text-muted-foreground">
                          Space links experience higher bit error rates due to atmospheric effects, distance, and interference. DTN includes robust error handling and retransmission.
                        </p>
                      </div>
                      <div>
                        <h4 className="font-semibold text-sm mb-1">Resource Constraints</h4>
                        <p className="text-sm text-muted-foreground">
                          Limited power, bandwidth, and storage on spacecraft require efficient protocols that minimize overhead and maximize data delivery probability.
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>DTN in Space Applications</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="list-disc list-inside space-y-2 text-sm text-muted-foreground ml-4">
                      <li><strong>ISS Communications:</strong> Reliable data transfer during brief ground station passes</li>
                      <li><strong>Mars Missions:</strong> Handling 3-22 minute light-time delays</li>
                      <li><strong>Lunar Networks:</strong> Supporting future lunar base communications</li>
                      <li><strong>Deep Space:</strong> Interplanetary internet for future exploration</li>
                      <li><strong>CubeSats:</strong> Low-cost satellite constellations with intermittent ground contact</li>
                    </ul>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Routing Tab */}
              <TabsContent value="routing" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>How Bundle Routing Works</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      Bundle routing in DTN differs fundamentally from Internet routing. Instead of finding a path at transmission time, DTN routing plans paths through a series of contacts (connection opportunities).
                    </p>
                    
                    <div className="space-y-4">
                      <div>
                        <h4 className="font-semibold text-sm mb-2">1. Contact Planning</h4>
                        <p className="text-sm text-muted-foreground mb-2">
                          The routing system maintains a <strong>contact graph</strong> that represents scheduled connection opportunities between nodes. Each contact has:
                        </p>
                        <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground ml-4">
                          <li>Start time and duration</li>
                          <li>Available data volume (bandwidth × duration)</li>
                          <li>Link quality metrics</li>
                        </ul>
                      </div>

                      <div>
                        <h4 className="font-semibold text-sm mb-2">2. Path Computation</h4>
                        <p className="text-sm text-muted-foreground mb-2">
                          When a bundle arrives, the router computes potential paths to the destination:
                        </p>
                        <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground ml-4">
                          <li>Identifies all possible contact sequences</li>
                          <li>Calculates earliest delivery time for each path</li>
                          <li>Considers bundle lifetime and size constraints</li>
                          <li>Selects the best path based on routing algorithm</li>
                        </ul>
                      </div>

                      <div>
                        <h4 className="font-semibold text-sm mb-2">3. Bundle Forwarding</h4>
                        <p className="text-sm text-muted-foreground mb-2">
                          The bundle is forwarded to the next hop when the contact becomes active:
                        </p>
                        <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground ml-4">
                          <li>Bundle is queued for the selected contact</li>
                          <li>Transmission occurs during contact window</li>
                          <li>Custody transfer confirms successful reception</li>
                          <li>Process repeats at each intermediate node</li>
                        </ul>
                      </div>

                      <div>
                        <h4 className="font-semibold text-sm mb-2">4. Store and Forward</h4>
                        <p className="text-sm text-muted-foreground">
                          If no immediate path exists, the bundle is stored in persistent storage until a suitable contact becomes available. This enables communication across disconnected network segments.
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Routing Algorithms</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <h4 className="font-semibold text-sm mb-2">Contact Graph Routing (CGR)</h4>
                      <p className="text-sm text-muted-foreground mb-2">
                        <strong>Used in this simulator.</strong> CGR is designed for space networks with predictable contacts. It:
                      </p>
                      <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground ml-4">
                        <li>Builds a graph from scheduled contacts</li>
                        <li>Computes shortest-delay paths using Dijkstra's algorithm</li>
                        <li>Considers contact capacity and bundle sizes</li>
                        <li>Is deterministic and predictable</li>
                      </ul>
                    </div>

                    <div>
                      <h4 className="font-semibold text-sm mb-2">Other Algorithms</h4>
                      <p className="text-sm text-muted-foreground">
                        See the Reference section for details on Epidemic Routing, Spray and Wait, and PROPHET algorithms used in ad-hoc and opportunistic networks.
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Link Budget Tab */}
              <TabsContent value="link-budget" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Link Budget Calculations</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      A <strong>link budget</strong> is an accounting of all gains and losses in a communication link. It determines whether a signal will be received with sufficient quality for reliable communication.
                    </p>

                    <div className="space-y-4">
                      <div>
                        <h4 className="font-semibold text-sm mb-2">Key Components</h4>
                        <div className="space-y-2 text-sm text-muted-foreground">
                          <div className="flex justify-between">
                            <span><strong>Transmit Power (P_t):</strong></span>
                            <span>Power output from transmitter (dBm or dBW)</span>
                          </div>
                          <div className="flex justify-between">
                            <span><strong>Antenna Gains (G_t, G_r):</strong></span>
                            <span>Directional gain of transmit/receive antennas (dBi)</span>
                          </div>
                          <div className="flex justify-between">
                            <span><strong>Path Loss (L_p):</strong></span>
                            <span>Signal attenuation over distance (dB)</span>
                          </div>
                          <div className="flex justify-between">
                            <span><strong>Noise Power (N):</strong></span>
                            <span>Thermal noise and interference (dBm)</span>
                          </div>
                        </div>
                      </div>

                      <div>
                        <h4 className="font-semibold text-sm mb-2">Calculation Steps</h4>
                        <ol className="list-decimal list-inside space-y-2 text-sm text-muted-foreground ml-4">
                          <li><strong>Calculate Path Loss:</strong> Use free space path loss formula based on distance and frequency</li>
                          <li><strong>Compute Received Power:</strong> P_r = P_t + G_t + G_r - L_p</li>
                          <li><strong>Determine Noise Level:</strong> N = k × T × B (thermal noise) plus interference</li>
                          <li><strong>Calculate SNR:</strong> SNR = P_r - N</li>
                          <li><strong>Check Link Margin:</strong> Margin = SNR - Required_SNR</li>
                        </ol>
                      </div>

                      <div>
                        <h4 className="font-semibold text-sm mb-2">ISS Link Budget Example</h4>
                        <div className="bg-muted p-3 rounded text-sm font-mono space-y-1">
                          <div>Transmit Power: 5 W = 37 dBm</div>
                          <div>Transmit Antenna Gain: 12 dBi</div>
                          <div>Receive Antenna Gain: 40 dBi</div>
                          <div>Distance: 400 km</div>
                          <div>Frequency: 2.4 GHz</div>
                          <div className="pt-2 border-t border-border">
                            Path Loss: ~152 dB<br/>
                            Received Power: ~-63 dBm<br/>
                            Noise Floor: ~-101 dBm<br/>
                            <strong>SNR: ~38 dB</strong>
                          </div>
                        </div>
                      </div>

                      <div>
                        <h4 className="font-semibold text-sm mb-2">Factors Affecting Link Budget</h4>
                        <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground ml-4">
                          <li><strong>Distance:</strong> Path loss increases with range (20 dB per decade)</li>
                          <li><strong>Frequency:</strong> Higher frequencies have higher path loss</li>
                          <li><strong>Atmospheric Effects:</strong> Rain, clouds, and ionosphere can add losses</li>
                          <li><strong>Antenna Pointing:</strong> Misalignment reduces effective gain</li>
                          <li><strong>Elevation Angle:</strong> Lower angles have longer paths through atmosphere</li>
                        </ul>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Handoff Tab */}
              <TabsContent value="handoff" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Handoff Procedures</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      A <strong>handoff</strong> (or handover) occurs when communication transfers from one ground station to another as a satellite moves across the sky. This is critical for maintaining continuous connectivity.
                    </p>

                    <div className="space-y-4">
                      <div>
                        <h4 className="font-semibold text-sm mb-2">Handoff Process</h4>
                        <ol className="list-decimal list-inside space-y-2 text-sm text-muted-foreground ml-4">
                          <li><strong>Prediction:</strong> System predicts when current station will lose visibility and which station will gain it</li>
                          <li><strong>Preparation:</strong> Next station's antenna begins tracking and establishes initial contact</li>
                          <li><strong>Transition:</strong> Active link transfers from outgoing to incoming station</li>
                          <li><strong>Verification:</strong> New link quality is verified and communication resumes</li>
                          <li><strong>Cleanup:</strong> Previous station releases resources and updates routing tables</li>
                        </ol>
                      </div>

                      <div>
                        <h4 className="font-semibold text-sm mb-2">Handoff Types</h4>
                        <div className="space-y-2 text-sm text-muted-foreground">
                          <div>
                            <strong>Hard Handoff:</strong> Connection breaks before new one establishes. Used when stations are far apart or have no overlap.
                          </div>
                          <div>
                            <strong>Soft Handoff:</strong> Both stations maintain connection simultaneously during transition. Requires overlapping coverage and coordination.
                          </div>
                        </div>
                      </div>

                      <div>
                        <h4 className="font-semibold text-sm mb-2">ISS Handoff Characteristics</h4>
                        <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground ml-4">
                          <li>ISS moves at ~7.66 km/s, completing an orbit in ~93 minutes</li>
                          <li>Typical ground station contact: 5-10 minutes</li>
                          <li>Handoffs occur every 5-15 minutes depending on station spacing</li>
                          <li>DTN handles handoffs gracefully by storing bundles during gaps</li>
                          <li>Multiple stations may be visible simultaneously, enabling mesh networking</li>
                        </ul>
                      </div>

                      <div>
                        <h4 className="font-semibold text-sm mb-2">DTN Advantages During Handoff</h4>
                        <p className="text-sm text-muted-foreground">
                          Unlike traditional protocols that fail during handoffs, DTN:
                        </p>
                        <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground ml-4">
                          <li>Stores bundles during handoff gaps</li>
                          <li>Automatically routes to next available station</li>
                          <li>Maintains delivery guarantees through custody transfer</li>
                          <li>Enables seamless multi-station communication</li>
                        </ul>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Protocol Stack Tab */}
              <TabsContent value="protocol" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>DTN Protocol Stack</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      The DTN architecture uses a layered protocol stack similar to the Internet, but adapted for challenged networks.
                    </p>

                    <div className="space-y-4">
                      <div>
                        <h4 className="font-semibold text-sm mb-3">Layer Structure</h4>
                        <div className="space-y-2">
                          {[
                            { name: "Application Layer", desc: "User applications (file transfer, messaging, telemetry)" },
                            { name: "Bundle Protocol", desc: "DTN-specific layer for store-and-forward messaging" },
                            { name: "Convergence Layer", desc: "Adapts BP to underlying transport (TCP, UDP, LTP)" },
                            { name: "Transport Layer", desc: "Reliable transport (TCP, LTP) or unreliable (UDP)" },
                            { name: "Network Layer", desc: "IP routing (when available) or DTN routing" },
                            { name: "Data Link Layer", desc: "Frame formatting, error detection (HDLC, Ethernet)" },
                            { name: "Physical Layer", desc: "Radio frequency transmission, modulation" },
                          ].map((layer, idx) => (
                            <div key={idx} className="border-l-2 border-primary pl-3 py-2">
                              <div className="font-semibold text-sm">{layer.name}</div>
                              <div className="text-xs text-muted-foreground">{layer.desc}</div>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div>
                        <h4 className="font-semibold text-sm mb-2">Bundle Protocol Layer</h4>
                        <p className="text-sm text-muted-foreground mb-2">
                          The core DTN layer that provides:
                        </p>
                        <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground ml-4">
                          <li><strong>Bundle Creation:</strong> Encapsulates application data with routing metadata</li>
                          <li><strong>Store and Forward:</strong> Persistent storage at intermediate nodes</li>
                          <li><strong>Custody Transfer:</strong> Reliable delivery through responsibility transfer</li>
                          <li><strong>Fragmentation:</strong> Splits large bundles for transmission over capacity-limited links</li>
                          <li><strong>Reassembly:</strong> Reconstructs fragmented bundles at destination</li>
                        </ul>
                      </div>

                      <div>
                        <h4 className="font-semibold text-sm mb-2">Convergence Layers</h4>
                        <div className="space-y-2 text-sm text-muted-foreground">
                          <div>
                            <strong>TCP Convergence Layer (TCPCL):</strong> Uses TCP for reliable delivery. Good for ground networks and stable links.
                          </div>
                          <div>
                            <strong>LTP Convergence Layer:</strong> Uses Licklider Transmission Protocol. Designed for space links with long delays and high error rates.
                          </div>
                          <div>
                            <strong>UDP Convergence Layer:</strong> Lightweight, unreliable transport. Used for low-latency applications that can tolerate loss.
                          </div>
                        </div>
                      </div>

                      <div>
                        <h4 className="font-semibold text-sm mb-2">Security (BPSec)</h4>
                        <p className="text-sm text-muted-foreground">
                          Bundle Protocol Security (BPSec) provides end-to-end security through security blocks that can provide integrity, confidentiality, and authentication services for bundles.
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>
        </ScrollArea>

        {/* Reference Section */}
        <div className="border-t p-6 bg-muted/30 flex-shrink-0">
          <div className="flex items-center gap-2 mb-4">
            <Search className="w-5 h-5" />
            <h3 className="text-lg font-semibold">Searchable Reference</h3>
          </div>
          <Input
            placeholder="Search DTN Bundle Protocol, routing algorithms, link budget formulas, orbital mechanics..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="mb-4"
          />
          <ScrollArea className="h-[200px]">
            <div className="space-y-3 pr-4">
              {filteredReferences.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No results found. Try different keywords.
                </p>
              ) : (
                filteredReferences.map((item) => (
                  <Card key={item.id}>
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-base">{item.title}</CardTitle>
                        <span className="text-xs px-2 py-1 bg-primary/10 text-primary rounded">
                          {item.category === "dtn" && "DTN"}
                          {item.category === "routing" && "Routing"}
                          {item.category === "link-budget" && "Link Budget"}
                          {item.category === "orbital" && "Orbital"}
                        </span>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground mb-2">{item.content}</p>
                      {item.formula && (
                        <div className="mt-3 p-3 bg-muted rounded font-mono text-xs whitespace-pre-wrap">
                          {item.formula}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))
              )}
            </div>
          </ScrollArea>
        </div>
      </SheetContent>
    </Sheet>
  );
};

export default EducationalPanel;

