import { useState, useEffect } from 'react';

export const useMET = () => {
  const [met, setMet] = useState<string>('000:00:00:00');

  useEffect(() => {
    // Mission start: November 20, 1998, 00:00:00 UTC
    const missionStart = new Date('1998-11-20T00:00:00Z');

    const updateMET = () => {
      const now = new Date();
      const diffMs = now.getTime() - missionStart.getTime();
      
      // Convert to seconds
      const totalSeconds = Math.floor(diffMs / 1000);

      const days = Math.floor(totalSeconds / 86400);
      const hours = Math.floor((totalSeconds % 86400) / 3600);
      const minutes = Math.floor((totalSeconds % 3600) / 60);
      const seconds = totalSeconds % 60;
      
      // Format as DDD:HH:MM:SS with zero padding
      const formatted = `${String(days).padStart(3, '0')}:${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
      
      setMet(formatted);
    };

    updateMET();

    const interval = setInterval(updateMET, 1000);

    return () => clearInterval(interval);
  }, []);

  return met;
};

