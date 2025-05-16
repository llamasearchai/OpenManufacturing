import React, { useState, useEffect, useCallback } from 'react';
import { Grid, Card, CardContent, Typography, Button, Box, CircularProgress, Tabs, Tab, TextField, Switch, FormControlLabel, Paper } from '@mui/material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { invoke } from '@tauri-apps/api/tauri';
import { listen, Event as TauriEvent } from '@tauri-apps/api/event';

// Define types based on Python Pydantic models and API responses
interface Device {
  id: string;
  name: string;
  type: string;
  status: string;
  // Add other relevant device fields
}

interface AlignmentPosition {
    x: number;
    y: number;
    z: number;
}

interface AlignmentResult {
    request_id: string;
    device_id: string;
    success: boolean;
    optical_power_dbm?: number;
    position?: AlignmentPosition;
    duration_ms?: number;
    timestamp: string; // ISO format string
    process_id?: string;
    error?: string;
    status?: string; // "completed", "failed", "in_progress" - from AlignmentTaskStatus
}

interface AlignmentParams {
    position_tolerance_um: number;
    angle_tolerance_deg: number;
    optical_power_threshold: number;
    max_iterations: number;
    use_machine_learning: boolean;
    // Add other parameters from AlignmentParametersRequest if needed
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div role="tabpanel" hidden={value !== index} id={`alignment-tabpanel-${index}`} aria-labelledby={`alignment-tab-${index}`} {...other}>
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

// Placeholder components (implement these properly)
const DeviceSelector: React.FC<{devices: Device[], selectedDevice: Device | null, onDeviceChange: (device: Device | null) => void}> = ({devices, selectedDevice, onDeviceChange}) => {
    return (
        <TextField 
            select 
            label="Select Device" 
            value={selectedDevice?.id || ''} 
            onChange={(e) => onDeviceChange(devices.find(d => d.id === e.target.value) || null)}
            fullWidth
            SelectProps={{ native: true }}
        >
            <option value=""></option>
            {devices.map(d => <option key={d.id} value={d.id}>{d.name} ({d.id})</option>)}
        </TextField>
    );
};

const AlignmentParametersEditor: React.FC<{parameters: AlignmentParams, onChange: (params: AlignmentParams) => void, disabled: boolean}> = ({parameters, onChange, disabled}) => {
    const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value, type, checked } = event.target;
        onChange({
            ...parameters,
            [name]: type === 'checkbox' ? checked : (type === 'number' ? parseFloat(value) : value),
        });
    };
    return (
        <Paper elevation={2} sx={{p: 2}}>
            <Typography variant="h6" gutterBottom>Alignment Parameters</Typography>
            <TextField label="Position Tolerance (µm)" name="position_tolerance_um" type="number" value={parameters.position_tolerance_um} onChange={handleChange} disabled={disabled} fullWidth margin="dense" />
            <TextField label="Angle Tolerance (deg)" name="angle_tolerance_deg" type="number" value={parameters.angle_tolerance_deg} onChange={handleChange} disabled={disabled} fullWidth margin="dense" />
            <TextField label="Optical Power Threshold (dBm)" name="optical_power_threshold" type="number" value={parameters.optical_power_threshold} onChange={handleChange} disabled={disabled} fullWidth margin="dense" />
            <TextField label="Max Iterations" name="max_iterations" type="number" value={parameters.max_iterations} onChange={handleChange} disabled={disabled} fullWidth margin="dense" />
            <FormControlLabel control={<Switch name="use_machine_learning" checked={parameters.use_machine_learning} onChange={handleChange} disabled={disabled} />} label="Use Machine Learning" />
        </Paper>
    );
};
const ProcessMonitor: React.FC = () => <Typography>Process Monitor (Placeholder)</Typography>;
const AlignmentHistoryDisplay: React.FC<{history: AlignmentResult[], onRefresh: () => void}> = ({history, onRefresh}) => {
    return (
        <Paper elevation={2} sx={{p:2}}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
                <Typography variant="h6">Alignment History</Typography>
                <Button onClick={onRefresh} size="small">Refresh</Button>
            </Box>
            {history.length === 0 && <Typography sx={{mt:1}}>No history available for selected device.</Typography>}
            {history.map((item, index) => (
                <Card key={index} sx={{my: 1}} variant="outlined">
                    <CardContent>
                        <Typography variant="body2">Request ID: {item.request_id}</Typography>
                        <Typography variant="body2">Timestamp: {new Date(item.timestamp).toLocaleString()}</Typography>
                        <Typography variant="body2">Status: {item.success ? 'Success' : 'Failed'} {item.error ? `(${item.error})` : ''}</Typography>
                        <Typography variant="body2">Power: {item.optical_power_dbm?.toFixed(2)} dBm</Typography>
                        {item.position && <Typography variant="body2">Position: X:{item.position.x.toFixed(3)} Y:{item.position.y.toFixed(3)} Z:{item.position.z.toFixed(3)} µm</Typography>}
                    </CardContent>
                </Card>
            ))}
        </Paper>
    );
};

const AlignmentDashboard: React.FC = () => {
  const [devices, setDevices] = useState<Device[]>([]);
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  const [alignmentParams, setAlignmentParams] = useState<AlignmentParams>({
    position_tolerance_um: 0.1,
    angle_tolerance_deg: 0.05,
    optical_power_threshold: -3.0,
    max_iterations: 100,
    use_machine_learning: true,
  });
  const [isAligning, setIsAligning] = useState(false);
  const [currentResult, setCurrentResult] = useState<AlignmentResult | null>(null);
  const [alignmentHistory, setAlignmentHistory] = useState<AlignmentResult[]>([]);
  const [powerData, setPowerData] = useState<any[]>([]);
  const [tabValue, setTabValue] = useState(0);
  const [activeRequestId, setActiveRequestId] = useState<string | null>(null);
  const [apiToken, setApiToken] = useState<string | null>(null); // Store API token

  // TODO: Implement API token retrieval (e.g., from a login screen or secure storage)
  useEffect(() => {
    // Placeholder for token retrieval
    const token = localStorage.getItem('api_token'); // Example: load from local storage
    if (token) setApiToken(token);
    else console.warn("API token not found. API calls may fail.");
  }, []);

  const apiInvoke = useCallback(async <T,>(command: string, args?: any): Promise<T> => {
    if (!apiToken) {
        console.error("API token is not available for invoke command:", command);
        // Potentially throw an error or trigger a login flow
        throw new Error("API token not available");
    }
    // Assuming your Tauri backend commands that call the FastAPI might need the token in headers
    // This example passes it as an argument to the Tauri command, which then adds it to HTTP headers.
    // Adjust based on how your Tauri command is structured.
    return invoke<T>(command, { ...args, apiToken });
  }, [apiToken]);

  const fetchDevices = useCallback(async () => {
    if (!apiToken) return;
    try {
      // Assumes a Tauri command `get_devices` that calls `/api/devices` endpoint
      const deviceList = await apiInvoke<Device[]>('get_devices_command'); // Replace with actual Tauri command
      setDevices(deviceList || []);
      if (deviceList && deviceList.length > 0 && !selectedDevice) {
        setSelectedDevice(deviceList[0]);
      }
    } catch (error) {
      console.error('Failed to fetch devices:', error);
      // Handle error (e.g., show notification)
    }
  }, [apiInvoke, selectedDevice, apiToken]);

  useEffect(() => {
    fetchDevices();
    const interval = setInterval(fetchDevices, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, [fetchDevices]);

  const fetchAlignmentHistory = useCallback(async () => {
    if (!selectedDevice || !apiToken) return;
    try {
      // Assumes Tauri command `get_alignment_history_command`
      const history = await apiInvoke<AlignmentResult[]>('get_alignment_history_command', {
        deviceId: selectedDevice.id,
        limit: 10
      });
      setAlignmentHistory(history || []);
    } catch (error) {
      console.error('Failed to fetch alignment history:', error);
    }
  }, [selectedDevice, apiInvoke, apiToken]);

  useEffect(() => {
    if (selectedDevice) {
      fetchAlignmentHistory();
    }
  }, [selectedDevice, fetchAlignmentHistory]);

  // Listen for real-time alignment updates (e.g., via WebSocket or SSE through Tauri)
  useEffect(() => {
    let unlistenFn: (() => void) | undefined;
    const setupListener = async () => {
        try {
            // Example: listen to a generic event that pushes updates for a request_id
            const unlisten = await listen<AlignmentResult>(`alignment_update_${activeRequestId}`, (event: TauriEvent<AlignmentResult>) => {
                console.log("Received alignment_update event:", event.payload);
                setCurrentResult(event.payload);

                if (event.payload.optical_power_dbm !== undefined && event.payload.position) {
                    setPowerData(prevData => {
                        const newPoint = {
                        time: new Date(event.payload.timestamp).toLocaleTimeString(),
                        power: event.payload.optical_power_dbm,
                        x: event.payload.position?.x,
                        y: event.payload.position?.y,
                        z: event.payload.position?.z,
                        };
                        return [...prevData, newPoint].slice(-50); // Keep last 50 points
                    });
                }

                if (event.payload.status === 'completed' || event.payload.status === 'failed' || event.payload.status === 'cancelled') {
                    setIsAligning(false);
                    setActiveRequestId(null); // Clear active request ID
                    fetchAlignmentHistory(); // Refresh history
                    // Potentially fetch final status via get_alignment_status_command if event payload is minimal
                }
            });
            unlistenFn = unlisten;
        } catch(e) {
            console.error("Failed to set up alignment_update listener for", activeRequestId, e);
        }
    };
    if(activeRequestId) {
        setupListener();
    }
    return () => {
      if (unlistenFn) {
        unlistenFn();
      }
    };
  }, [activeRequestId, fetchAlignmentHistory]); // Re-subscribe if activeRequestId changes

  const handleStartAlignment = async () => {
    if (!selectedDevice || !apiToken) return;
    try {
      setIsAligning(true);
      setPowerData([]);
      setCurrentResult(null);
      
      // Assumes Tauri command `start_alignment_command` that calls POST /api/alignment/start
      const response = await apiInvoke<{ request_id: string, status: string, message?: string }>('start_alignment_command', {
        deviceId: selectedDevice.id,
        parameters: alignmentParams // This should match AlignmentParametersRequest in Python
      });
      
      setActiveRequestId(response.request_id);
      // Initial status update
      setCurrentResult({
        request_id: response.request_id, 
        device_id: selectedDevice.id, 
        success: false, 
        status: response.status, 
        timestamp: new Date().toISOString()
      });

    } catch (error) {
      console.error('Failed to start alignment:', error);
      setIsAligning(false);
      // Display error to user
    }
  };

  const handleCancelAlignment = async () => {
    if (!activeRequestId || !apiToken) return;
    try {
      // Assumes Tauri command `cancel_alignment_command`
      await apiInvoke('cancel_alignment_command', { alignment_request_id: activeRequestId });
      // Status update will come via the event listener or by polling get_alignment_status
      // For immediate feedback:
      // setIsAligning(false); 
      // setActiveRequestId(null);
    } catch (error) {
      console.error('Failed to cancel alignment:', error);
    }
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  return (
    <Grid container spacing={3} sx={{p: 2}}>
      <Grid item xs={12}>
        <Card>
          <CardContent>
            <Typography variant="h4" component="h1" gutterBottom>
              Optical Alignment Dashboard
            </Typography>
            {!apiToken && <Typography color="error">API Token not set. Functionality may be limited.</Typography>}
            <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
              <Tabs value={tabValue} onChange={handleTabChange} aria-label="alignment dashboard tabs">
                <Tab label="Alignment Control" id="alignment-tab-0" />
                <Tab label="Process Monitor" id="alignment-tab-1" />
                <Tab label="History" id="alignment-tab-2" />
              </Tabs>
            </Box>
            
            <TabPanel value={tabValue} index={0}>
              <Grid container spacing={3} sx={{mt: 1}}>
                <Grid item xs={12} md={4}>
                  <DeviceSelector devices={devices} selectedDevice={selectedDevice} onDeviceChange={setSelectedDevice} />
                  <Box mt={2}>
                    <AlignmentParametersEditor parameters={alignmentParams} onChange={setAlignmentParams} disabled={isAligning} />
                  </Box>
                  <Box mt={2} display="flex" justifyContent="center">
                    {isAligning && activeRequestId ? (
                      <Button variant="contained" color="secondary" onClick={handleCancelAlignment} startIcon={<CircularProgress size={20} color="inherit" />}>
                        Cancel Alignment ({activeRequestId.substring(0,8)}...)
                      </Button>
                    ) : (
                      <Button variant="contained" color="primary" onClick={handleStartAlignment} disabled={!selectedDevice || !apiToken || isAligning}>
                        Start Alignment
                      </Button>
                    )}
                  </Box>
                </Grid>
                
                <Grid item xs={12} md={8}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="h6" gutterBottom>Real-time Optical Power</Typography>
                      <ResponsiveContainer width="100%" height={250}>
                        <LineChart data={powerData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="time" />
                          <YAxis yAxisId="left" orientation="left" domain={['auto', 'auto']} label={{ value: 'Power (dBm)', angle: -90, position: 'insideLeft' }}/>
                          <Tooltip />
                          <Legend />
                          <Line yAxisId="left" type="monotone" dataKey="power" stroke="#8884d8" name="Optical Power (dBm)" dot={false} isAnimationActive={false}/>
                        </LineChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                  
                  {currentResult && (
                    <Card variant="outlined" sx={{ mt: 2 }}>
                      <CardContent>
                        <Typography variant="h6" gutterBottom>Current Alignment Status (Request: {currentResult.request_id.substring(0,8)}...)</Typography>
                        <Grid container spacing={1}>
                          <Grid item xs={12} sm={6}><Typography variant="body2">Device ID: {currentResult.device_id}</Typography></Grid>
                          <Grid item xs={12} sm={6}><Typography variant="body2">Status: 
                            <span style={{color: currentResult.status === 'completed' && currentResult.success ? 'green' : (currentResult.status === 'failed' || (currentResult.status === 'completed' && !currentResult.success) ? 'red' : 'blue')}}>
                                {currentResult.status}
                            </span>
                          </Typography></Grid>
                          {currentResult.optical_power_dbm !== undefined && <Grid item xs={6} sm={3}><Typography variant="body2">Power: {currentResult.optical_power_dbm.toFixed(2)} dBm</Typography></Grid>}
                          {currentResult.position && (
                            <>
                                <Grid item xs={6} sm={3}><Typography variant="body2">X: {currentResult.position.x.toFixed(3)} µm</Typography></Grid>
                                <Grid item xs={6} sm={3}><Typography variant="body2">Y: {currentResult.position.y.toFixed(3)} µm</Typography></Grid>
                                <Grid item xs={6} sm={3}><Typography variant="body2">Z: {currentResult.position.z.toFixed(3)} µm</Typography></Grid>
                            </>
                          )}
                          {currentResult.duration_ms !== undefined && <Grid item xs={6}><Typography variant="body2">Duration: {(currentResult.duration_ms / 1000).toFixed(1)} s</Typography></Grid>}
                          <Grid item xs={12}><Typography variant="body2">Timestamp: {new Date(currentResult.timestamp).toLocaleString()}</Typography></Grid>
                          {currentResult.error && <Grid item xs={12}><Typography variant="body2" color="error">Error: {currentResult.error}</Typography></Grid>}
                        </Grid>
                      </CardContent>
                    </Card>
                  )}
                </Grid>
              </Grid>
            </TabPanel>
            
            <TabPanel value={tabValue} index={1}>
              <ProcessMonitor />
            </TabPanel>
            
            <TabPanel value={tabValue} index={2}>
              <AlignmentHistoryDisplay history={alignmentHistory} onRefresh={fetchAlignmentHistory} />
            </TabPanel>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
};

export default AlignmentDashboard; 