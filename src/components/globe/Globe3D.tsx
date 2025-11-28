import { useRef, useMemo, Suspense } from 'react';
import { Canvas, useFrame, useLoader } from '@react-three/fiber';
import { OrbitControls, Stars, Html } from '@react-three/drei';
import * as THREE from 'three';

interface Globe3DProps {
  issPosition: {
    latitude: number;
    longitude: number;
    altitude_km: number;
    velocity_kmps?: number;
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

// Orbital Path Trail
function OrbitalPath({ radius }: { radius: number }) {
  const points = useMemo(() => {
    const orbitPoints = [];
    const segments = 128;
    for (let i = 0; i <= segments; i++) {
      const angle = (i / segments) * Math.PI * 2;
      orbitPoints.push(
        new THREE.Vector3(
          Math.cos(angle) * radius,
          Math.sin(angle) * radius * 0.1, // Slight tilt
          Math.sin(angle) * radius
        )
      );
    }
    return orbitPoints;
  }, [radius]);

  const curve = useMemo(() => new THREE.CatmullRomCurve3(points, true), [points]);

  return (
    <mesh>
      <tubeGeometry args={[curve, 256, 0.015, 8, true]} />
      <meshBasicMaterial color="#00ff00" transparent opacity={0.3} />
    </mesh>
  );
}

// ISS Satellite
function ISS({ position }: { position: { latitude: number; longitude: number; altitude_km: number; velocity_kmps?: number } }) {
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
      {/* Orbital Path */}
      <OrbitalPath radius={radius} />

      {/* ISS Info Panel */}
      <Html position={[issPosition.x, issPosition.y + 0.5, issPosition.z]} center distanceFactor={15}>
        <div
          className="px-3 py-2 rounded-lg text-xs font-mono whitespace-nowrap pointer-events-none transition-all duration-300"
          style={{
            background: 'rgba(0, 255, 0, 0.1)',
            border: '1px solid rgba(0, 255, 0, 0.4)',
            color: '#00ff00',
            backdropFilter: 'blur(12px)',
            boxShadow: '0 0 20px rgba(0, 255, 0, 0.3), inset 0 0 20px rgba(0, 255, 0, 0.1)',
          }}
        >
          <div className="font-bold mb-1">🛰️ ISS</div>
          <div className="text-[9px] opacity-80">
            {position.altitude_km.toFixed(1)} km • {position.velocity_kmps ? `${position.velocity_kmps.toFixed(2)} km/s` : '7.66 km/s'}
          </div>
        </div>
      </Html>

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

// Ground Station Marker
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
      {/* Station marker */}
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

      {/* Station Label */}
      <Html position={[stationPos.x, stationPos.y + 0.3, stationPos.z]} center distanceFactor={10}>
        <div
          className="px-2 py-1 rounded text-[10px] font-mono whitespace-nowrap pointer-events-none transition-all duration-300"
          style={{
            background: `${stationColor}20`,
            border: `1px solid ${stationColor}60`,
            color: stationColor,
            backdropFilter: 'blur(8px)',
            boxShadow: `0 0 10px ${stationColor}40`,
            opacity: station.is_visible ? 1 : 0.6,
            transform: station.is_visible ? 'scale(1.05)' : 'scale(1)',
          }}
        >
          {station.name}
        </div>
      </Html>
    </group>
  );
}

// Connection Lines
function ConnectionLines({
  groundStations,
  issPosition,
}: {
  groundStations: Array<{
    id: string;
    lat: number;
    lon: number;
    color: string;
    is_visible?: boolean;
  }>;
  issPosition: { latitude: number; longitude: number; altitude_km: number };
}) {
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

  const visibleStations = useMemo(
    () => groundStations.filter((station) => station.is_visible),
    [groundStations]
  );

  return (
    <group>
      {visibleStations.map((station) => {
        const stationPos = latLonToVector3(station.lat, station.lon, earthRadius + 0.02);
        const curve = new THREE.CatmullRomCurve3([stationPos, issPos]);
        
        return (
          <mesh key={`connection-${station.id}`}>
            <tubeGeometry args={[curve, 32, 0.008, 8, false]} />
            <meshBasicMaterial color={station.color} transparent opacity={0.4} />
          </mesh>
        );
      })}
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

// The main Rotating World component
function RotatingWorld({
  groundStations,
  issPosition,
}: {
  groundStations: Array<{
    id: string;
    name: string;
    lat: number;
    lon: number;
    color: string;
    is_visible?: boolean;
  }>;
  issPosition: { latitude: number; longitude: number; altitude_km: number; velocity_kmps?: number };
}) {
  const groupRef = useRef<THREE.Group>(null);
  const cloudsRef = useRef<THREE.Mesh>(null);

  // Load textures
  const [earthDayMap, earthNightMap, cloudsMap, earthSpecularMap] = useLoader(THREE.TextureLoader, [
    'https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/earth_atmos_2048.jpg',
    'https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/earth_lights_2048.png',
    'https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/earth_clouds_1024.png',
    'https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/earth_specular_2048.jpg',
  ]);

  // Rotate the entire world group slowly
  useFrame(() => {
    if (groupRef.current) {
      // Slower, more realistic-feeling rotation
      groupRef.current.rotation.y += 0.0001; 
    }
    // Clouds rotate slightly relative to the earth
    if (cloudsRef.current) {
      cloudsRef.current.rotation.y += 0.00005; 
    }
  });

  return (
    <group ref={groupRef}>
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
      
      {/* Ground Stations */}
      {groundStations.map((station) => (
        <GroundStationMarker
          key={station.id}
          station={station}
        />
      ))}

      {/* ISS */}
      <ISS position={issPosition} />

      {/* Connection Lines */}
      <ConnectionLines
        groundStations={groundStations}
        issPosition={issPosition}
      />
    </group>
  );
}

// Main Scene
function Scene({ issPosition, groundStations }: Globe3DProps) {
  return (
    <>
      {/* Enhanced lighting setup */}
      <ambientLight intensity={0.2} />
      <directionalLight
        position={[10, 5, 10]}
        intensity={1.5}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
      />
      <directionalLight position={[-8, -4, -8]} intensity={0.4} color="#4080ff" />
      <pointLight position={[0, 10, 0]} intensity={0.3} color="#ffffff" distance={30} />
      <pointLight position={[-15, 0, 0]} intensity={0.5} color="#60a5fa" distance={25} />

      {/* Background stars */}
      <Stars radius={100} depth={50} count={5000} factor={4} saturation={0} fade speed={1} />

      {/* Rotating Earth System */}
      <Suspense fallback={<LoadingFallback />}>
        <RotatingWorld 
          issPosition={issPosition}
          groundStations={groundStations}
        />
        <Atmosphere />
      </Suspense>

      {/* Orbit controls */}
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
