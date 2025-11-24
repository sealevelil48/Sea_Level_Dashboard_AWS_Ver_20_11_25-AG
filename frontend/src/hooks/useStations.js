import { useState, useCallback, useEffect, useRef } from 'react';
import apiService from '../services/apiService';

const FALLBACK_STATIONS = ['All Stations', 'Acre', 'Ashdod', 'Ashkelon', 'Eilat', 'Haifa', 'Yafo'];

export const useStations = () => {
  const [stations, setStations] = useState([]);
  const [selectedStations, setSelectedStations] = useState(['All Stations']);
  const [stationsFetched, setStationsFetched] = useState(false);
  const [loading, setLoading] = useState(false);
  const isMounted = useRef(true);

  // Cleanup on unmount
  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  // Fetch stations on mount
  useEffect(() => {
    const loadStations = async () => {
      if (stationsFetched) return;

      setLoading(true);
      try {
        const result = await apiService.getStations().catch(err => {
          console.error('Stations fetch failed:', err);
          return { stations: FALLBACK_STATIONS, database_available: false };
        });

        if (isMounted.current) {
          setStations(result.stations || FALLBACK_STATIONS);
          setStationsFetched(true);
        }
      } catch (error) {
        console.error('Stations load error:', error);
        if (isMounted.current) {
          setStations(FALLBACK_STATIONS);
          setStationsFetched(true);
        }
      } finally {
        if (isMounted.current) {
          setLoading(false);
        }
      }
    };

    loadStations();
  }, [stationsFetched]);

  // Handle station selection (support multi-select up to 3)
  // Matches the exact logic from Dashboard.js lines 776-790
  const handleStationChange = useCallback((value) => {
    if (value === 'All Stations') {
      setSelectedStations(['All Stations']);
    } else {
      setSelectedStations(prev => {
        if (prev.includes(value)) {
          // Deselect - matching Dashboard.js behavior (no fallback to All Stations)
          return prev.filter(s => s !== value);
        } else if (prev.length < 3 && !prev.includes('All Stations')) {
          // Add to selection (max 3)
          return [...prev, value];
        } else {
          // Replace selection (when at max or switching from All Stations)
          return [value];
        }
      });
    }
  }, []);

  // Get stations to fetch (excludes 'All Stations')
  const stationsToFetch = useCallback(() => {
    if (selectedStations.includes('All Stations')) {
      return stations.filter(s => s !== 'All Stations');
    }
    return selectedStations;
  }, [selectedStations, stations]);

  return {
    stations,
    selectedStations,
    setSelectedStations,
    stationsFetched,
    loading,
    handleStationChange,
    stationsToFetch
  };
};

export default useStations;
