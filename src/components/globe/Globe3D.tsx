import { useRef, useMemo, Suspense } from 'react';
import { Canvas, useFrame, useLoader } from '@react-three/fiber';
import { OrbitControls, Stars } from '@react-three/drei';
import * as THREE from 'three';

interface Globe3DProps {
  issPosition: {
    latitude: number;
    longitude: number;
    altitude_km: number;
  };
  groundStations: Array<{
    id: string;
    name: string;
    lat: number;
    lon: number;
    color: string;
    is_visible?: boolean;
  }>;
  orbitalPath?: Array<{ lat: number; lon: number; alt: number }>;
}

// Convert lat/lon to 3D coordinates on sphere
function latLonToVector3(lat: number, lon: number, radius: number): THREE.Vector3 {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);

  const x = -(radius * Math.sin(phi) * Math.cos(theta));
  const z = radius * Math.sin(phi) * Math.sin(theta);
  const y = radius * Math.cos(phi);

  return new THREE.Vector3(x, y, z);
}

// Atmosphere glow effect
function Atmosphere() {
  const shaderMaterial = useMemo(() => {
    return new THREE.ShaderMaterial({
      vertexShader: `
        varying vec3 vNormal;
        void main() {
          vNormal = normalize(normalMatrix * normal);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        varying vec3 vNormal;
        void main() {
          float intensity = pow(0.6 - dot(vNormal, vec3(0, 0, 1.0)), 2.0);
          gl_FragColor = vec4(0.3, 0.6, 1.0, 1.0) * intensity;
        }
      `,
      side: THREE.BackSide,
      blending: THREE.AdditiveBlending,
      transparent: true,
    });
  }, []);

  return (
    <mesh scale={1.15}>
      <sphereGeometry args={[5, 64, 64]} />
      <primitive object={shaderMaterial} attach="material" />
    </mesh>
  );
}

// ISS Satellite
function ISS({ position }: { position: { latitude: number; longitude: number; altitude_km: number } }) {
  const issRef = useRef<THREE.Group>(null);
  const earthRadius = 5;
  const altitudeScale = 0.01;
  const radius = earthRadius + position.altitude_km * altitudeScale;

  const issPosition = useMemo(() =>
    latLonToVector3(position.latitude, position.longitude, radius),
    [position.latitude, position.longitude, radius]
  );

  // Rotate ISS to face forward
  useFrame(() => {
    if (issRef.current) {
      issRef.current.lookAt(0, 0, 0);
    }
  });

  return (
    <group>
      {/* ISS Model */}
      <group ref={issRef} position={issPosition}>
        {/* Central body */}
        <mesh>
          <boxGeometry args={[0.2, 0.12, 0.12]} />
          <meshStandardMaterial color="#e0e0e0" metalness={0.8} roughness={0.3} />
        </mesh>

        {/* Solar panels - left */}
        <mesh position={[-0.25, 0, 0]}>
          <boxGeometry args={[0.18, 0.35, 0.02]} />
          <meshStandardMaterial color="#1e40af" metalness={0.9} roughness={0.1} />
        </mesh>

        {/* Solar panels - right */}
        <mesh position={[0.25, 0, 0]}>
          <boxGeometry args={[0.18, 0.35, 0.02]} />
          <meshStandardMaterial color="#1e40af" metalness={0.9} roughness={0.1} />
        </mesh>

        {/* Antenna */}
        <mesh position={[0, 0.08, 0]}>
          <cylinderGeometry args={[0.01, 0.01, 0.1]} />
          <meshStandardMaterial color="#ff0000" emissive="#ff0000" emissiveIntensity={0.5} />
        </mesh>

        {/* Glow effect */}
        <pointLight color="#00ff00" intensity={2} distance={3} />

        {/* Outer glow */}
        <mesh>
          <sphereGeometry args={[0.3, 16, 16]} />
          <meshBasicMaterial color="#00ff00" transparent opacity={0.1} />
        </mesh>
      </group>
    </group>
  );
}

// Ground Station Marker (renders on Earth surface, rotates with Earth)
function GroundStationMarker({
  station,
}: {
  station: {
    id: string;
    name: string;
    lat: number;
    lon: number;
    color: string;
    is_visible?: boolean;
  };
}) {
  const earthRadius = 5;
  const stationPos = useMemo(() =>
    latLonToVector3(station.lat, station.lon, earthRadius + 0.02),
    [station.lat, station.lon]
  );

  const stationColor = station.color || '#888888';
  const emissiveIntensity = station.is_visible ? 1.0 : 0.3;

  return (
    <group>
      {/* Station marker - taller pin */}
      <group position={stationPos}>
        {/* Pin base */}
        <mesh>
          <sphereGeometry args={[0.06, 16, 16]} />
          <meshStandardMaterial
            color={stationColor}
            emissive={stationColor}
            emissiveIntensity={emissiveIntensity}
          />
        </mesh>

        {/* Pin pole */}
        <mesh position={[0, 0.08, 0]}>
          <cylinderGeometry args={[0.01, 0.01, 0.16, 8]} />
          <meshStandardMaterial
            color={stationColor}
            emissive={stationColor}
            emissiveIntensity={emissiveIntensity * 0.5}
          />
        </mesh>

        {/* Top sphere */}
        <mesh position={[0, 0.16, 0]}>
          <sphereGeometry args={[0.03, 12, 12]} />
          <meshStandardMaterial
            color={stationColor}
            emissive={stationColor}
            emissiveIntensity={emissiveIntensity}
          />
        </mesh>
      </group>

      {/* Outer ring */}
      <mesh position={stationPos} rotation={[Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.08, 0.1, 32]} />
        <meshBasicMaterial color={stationColor} transparent opacity={0.5} side={THREE.DoubleSide} />
      </mesh>

      {/* Point light for glow */}
      <pointLight position={stationPos} color={stationColor} intensity={station.is_visible ? 1 : 0.3} distance={0.5} />
    </group>
  );
}

// Connection Lines (in world space, connecting rotating stations to ISS)
function ConnectionLines({
  groundStations,
  issPosition,
  earthGroupRef,
}: {
  groundStations: Array<{
    id: string;
    name: string;
    lat: number;
    lon: number;
    color: string;
    is_visible?: boolean;
  }>;
  issPosition: { latitude: number; longitude: number; altitude_km: number };
  earthGroupRef: React.RefObject<THREE.Group>;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const earthRadius = 5;
  const altitudeScale = 0.01;

  const issPos = useMemo(() =>
    latLonToVector3(
      issPosition.latitude,
      issPosition.longitude,
      earthRadius + issPosition.altitude_km * altitudeScale
    ),
    [issPosition.latitude, issPosition.longitude, issPosition.altitude_km]
  );

  // Update connection lines each frame based on Earth rotation
  useFrame(() => {
    if (!earthGroupRef.current || !groupRef.current) return;

    const earthRotation = earthGroupRef.current.rotation.y;

    // Update each visible station's connection line
    groundStations
      .filter((station) => station.is_visible)
      .forEach((station, index) => {
        const child = groupRef.current?.children[index];
        if (!child || !(child instanceof THREE.Mesh)) return;

        // Calculate station position in world space
        const stationLocalPos = latLonToVector3(station.lat, station.lon, earthRadius + 0.02);
        const rotatedStationPos = stationLocalPos.clone().applyAxisAngle(
          new THREE.Vector3(0, 1, 0),
          earthRotation
        );

        // Update geometry
        const curve = new THREE.CatmullRomCurve3([rotatedStationPos, issPos]);
        const newGeometry = new THREE.TubeGeometry(curve, 32, 0.008, 8, false);
        child.geometry.dispose();
        child.geometry = newGeometry;
      });
  });

  const visibleStations = useMemo(
    () => groundStations.filter((station) => station.is_visible),
    [groundStations]
  );

  return (
    <group ref={groupRef}>
      {visibleStations.map((station) => (
        <mesh key={`connection-${station.id}`}>
          <tubeGeometry
            args={[
              new THREE.CatmullRomCurve3([
                new THREE.Vector3(0, 0, 0),
                new THREE.Vector3(0, 0, 0),
              ]),
              32,
              0.008,
              8,
              false,
            ]}
          />
          <meshBasicMaterial color={station.color} transparent opacity={0.4} />
        </mesh>
      ))}
    </group>
  );
}

// Loading fallback
function LoadingFallback() {
  return (
    <mesh>
      <sphereGeometry args={[5, 32, 32]} />
      <meshBasicMaterial color="#1e40af" wireframe />
    </mesh>
  );
}

// Wrapper for Earth that exposes its rotation ref
function EarthWithStations({
  groundStations,
  issPosition,
  earthGroupRef,
}: {
  groundStations: Array<{
    id: string;
    name: string;
    lat: number;
    lon: number;
    color: string;
    is_visible?: boolean;
  }>;
  issPosition: { latitude: number; longitude: number; altitude_km: number };
  earthGroupRef: React.RefObject<THREE.Group>;
}) {
  const cloudsRef = useRef<THREE.Mesh>(null);

  // Load textures from public URLs
  const [earthDayMap, earthNightMap, cloudsMap, earthSpecularMap] = useLoader(THREE.TextureLoader, [
    'https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/earth_atmos_2048.jpg',
    'https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/earth_lights_2048.png',
    'https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/earth_clouds_1024.png',
    'https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/earth_specular_2048.jpg',
  ]);

  // Rotate Earth, clouds, and stations together
  useFrame(() => {
    if (earthGroupRef.current) {
      earthGroupRef.current.rotation.y += 0.001;
    }
    if (cloudsRef.current) {
      cloudsRef.current.rotation.y += 0.0012; // Clouds rotate slightly faster
    }
  });

  return (
    <group>
      {/* Earth group that rotates with stations */}
      <group ref={earthGroupRef}>
        {/* Main Earth sphere */}
        <mesh>
          <sphereGeometry args={[5, 64, 64]} />
          <meshPhongMaterial
            map={earthDayMap}
            emissiveMap={earthNightMap}
            emissive={new THREE.Color(0xffff88)}
            emissiveIntensity={0.8}
            specularMap={earthSpecularMap}
            specular={new THREE.Color(0x333333)}
            shininess={10}
          />
        </mesh>

        {/* Ground Stations - inside Earth group so they rotate with it */}
        {groundStations.map((station) => (
          <GroundStationMarker
            key={station.id}
            station={station}
          />
        ))}
      </group>

      {/* Cloud layer */}
      <mesh ref={cloudsRef}>
        <sphereGeometry args={[5.02, 64, 64]} />
        <meshPhongMaterial
          map={cloudsMap}
          transparent
          opacity={0.4}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}

// Main Scene
function Scene({ issPosition, groundStations }: Globe3DProps) {
  const earthGroupRef = useRef<THREE.Group>(null);

  return (
    <>
      {/* Lighting setup for realistic Earth */}
      <ambientLight intensity={0.15} />
      <directionalLight position={[5, 3, 5]} intensity={1.2} />
      <directionalLight position={[-5, -3, -5]} intensity={0.3} />

      {/* Background stars */}
      <Stars radius={100} depth={50} count={5000} factor={4} saturation={0} fade speed={1} />

      {/* Earth with texture loading - includes ground stations */}
      <Suspense fallback={<LoadingFallback />}>
        <EarthWithStations
          groundStations={groundStations}
          issPosition={issPosition}
          earthGroupRef={earthGroupRef}
        />
        <Atmosphere />
      </Suspense>

      {/* ISS */}
      <ISS position={issPosition} />

      {/* Connection lines in world space */}
      <ConnectionLines
        groundStations={groundStations}
        issPosition={issPosition}
        earthGroupRef={earthGroupRef}
      />

      {/* Camera controls */}
      <OrbitControls
        enablePan={true}
        enableZoom={true}
        enableRotate={true}
        minDistance={8}
        maxDistance={30}
        autoRotate={false}
        autoRotateSpeed={0.5}
      />
    </>
  );
}

// Main Globe3D Component
export default function Globe3D({ issPosition, groundStations, orbitalPath }: Globe3DProps) {
  return (
    <div style={{ width: '100%', height: '100%', background: '#000' }}>
      <Canvas
        camera={{
          position: [0, 0, 15],
          fov: 50,
        }}
        gl={{ antialias: true, alpha: false }}
      >
        <Scene
          issPosition={issPosition}
          groundStations={groundStations}
          orbitalPath={orbitalPath}
        />
      </Canvas>
    </div>
  );
}
