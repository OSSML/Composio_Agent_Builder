import { useState, useEffect } from 'react';
import {
  Assistant,
  getAssistant,
  CronJob,
  CronRun,
  listCrons,
  createCron,
  updateCron,
  deleteCron,
  runCronNow,
  listCronRuns,
  checkToolkitConnections,
} from '../lib/api';
import { Button } from './ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Switch } from './ui/switch';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from './ui/tooltip';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from './ui/alert-dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from './ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import {
  ArrowLeft,
  Plus,
  Clock,
  Trash2,
  Edit,
  Play,
  Link2 as LinkIcon,
  Loader2,
  FileText,
  CheckCircle,
  XCircle,
  MessageSquare,
  Maximize2,
  Download,
  ChevronDown,
} from 'lucide-react';
import { toast } from 'sonner';
import { ToolkitConnectionManager } from './ToolkitConnectionManager';
import ReactMarkdown from 'react-markdown';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';

interface AssistantDashboardProps {
  assistant: Assistant;
  onBack: () => void;
  onOpenChat?: () => void;
}

// Custom Cron Scheduler Component with sentence-like interface
function CronScheduler({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const [frequency, setFrequency] = useState('daily');
  const [minute, setMinute] = useState('0');
  const [hour, setHour] = useState('0');
  const [ampm, setAmpm] = useState('AM');
  const [dayOfWeek, setDayOfWeek] = useState('0');
  const [dayOfMonth, setDayOfMonth] = useState('1');

  // Parse initial cron value
  useEffect(() => {
    const parts = value.split(' ');
    if (parts.length === 5) {
      const [min, hr, dom, mon, dow] = parts;

      // Detect frequency type
      if (min === '*/15' && hr === '*') {
        setFrequency('15min');
      } else if (min === '*/30' && hr === '*') {
        setFrequency('30min');
      } else if (min !== '*' && hr === '*') {
        setFrequency('hourly');
        setMinute(min);
      } else if (dom === '*' && mon === '*' && dow === '*') {
        setFrequency('daily');
        const hourNum = parseInt(hr);
        if (hourNum >= 12) {
          setHour(String(hourNum === 12 ? 12 : hourNum - 12));
          setAmpm('PM');
        } else {
          setHour(String(hourNum === 0 ? 12 : hourNum));
          setAmpm('AM');
        }
        setMinute(min);
      } else if (dom === '*' && mon === '*' && dow !== '*') {
        setFrequency('weekly');
        setDayOfWeek(dow);
        const hourNum = parseInt(hr);
        if (hourNum >= 12) {
          setHour(String(hourNum === 12 ? 12 : hourNum - 12));
          setAmpm('PM');
        } else {
          setHour(String(hourNum === 0 ? 12 : hourNum));
          setAmpm('AM');
        }
        setMinute(min);
      } else if (dow === '*' && mon === '*') {
        setFrequency('monthly');
        setDayOfMonth(dom);
        const hourNum = parseInt(hr);
        if (hourNum >= 12) {
          setHour(String(hourNum === 12 ? 12 : hourNum - 12));
          setAmpm('PM');
        } else {
          setHour(String(hourNum === 0 ? 12 : hourNum));
          setAmpm('AM');
        }
        setMinute(min);
      }
    }
  }, []);

  // Update cron expression when values change
  useEffect(() => {
    let cronExpression = '';

    switch (frequency) {
      case '15min':
        cronExpression = '*/15 * * * *';
        break;
      case '30min':
        cronExpression = '*/30 * * * *';
        break;
      case 'hourly':
        cronExpression = `${minute} * * * *`;
        break;
      case 'daily':
        const dailyHour = ampm === 'PM' ? (parseInt(hour) === 12 ? 12 : parseInt(hour) + 12) : (parseInt(hour) === 12 ? 0 : parseInt(hour));
        cronExpression = `${minute} ${dailyHour} * * *`;
        break;
      case 'weekly':
        const weeklyHour = ampm === 'PM' ? (parseInt(hour) === 12 ? 12 : parseInt(hour) + 12) : (parseInt(hour) === 12 ? 0 : parseInt(hour));
        cronExpression = `${minute} ${weeklyHour} * * ${dayOfWeek}`;
        break;
      case 'monthly':
        const monthlyHour = ampm === 'PM' ? (parseInt(hour) === 12 ? 12 : parseInt(hour) + 12) : (parseInt(hour) === 12 ? 0 : parseInt(hour));
        cronExpression = `${minute} ${monthlyHour} ${dayOfMonth} * *`;
        break;
    }

    onChange(cronExpression);
  }, [frequency, minute, hour, ampm, dayOfWeek, dayOfMonth]);

  const frequencyLabels = {
    '15min': 'every 15 minutes',
    '30min': 'every 30 minutes',
    'hourly': 'hour',
    'daily': 'day',
    'weekly': 'week',
    'monthly': 'month'
  };

  const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const minuteOptions = [0, 15, 30, 45];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">Run</span>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 transition-colors">
              <span className="font-medium">{frequencyLabels[frequency as keyof typeof frequencyLabels]}</span>
              <ChevronDown className="w-3 h-3" />
            </button>
          </DropdownMenuTrigger>
          {/* MODIFIED: Added className */}
          <DropdownMenuContent align="start" className="bg-white">
            <DropdownMenuItem onClick={() => setFrequency('15min')}>every 15 minutes</DropdownMenuItem>
            <DropdownMenuItem onClick={() => setFrequency('30min')}>every 30 minutes</DropdownMenuItem>
            <DropdownMenuItem onClick={() => setFrequency('hourly')}>hour</DropdownMenuItem>
            <DropdownMenuItem onClick={() => setFrequency('daily')}>day</DropdownMenuItem>
            <DropdownMenuItem onClick={() => setFrequency('weekly')}>week</DropdownMenuItem>
            <DropdownMenuItem onClick={() => setFrequency('monthly')}>month</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {frequency === 'weekly' && (
          <>
            <span>on</span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 transition-colors">
                  <span className="font-medium">{dayNames[parseInt(dayOfWeek)]}</span>
                  <ChevronDown className="w-3 h-3" />
                </button>
              </DropdownMenuTrigger>
              {/* MODIFIED: Added className */}
              <DropdownMenuContent align="start" className="bg-white">
                {dayNames.map((day, idx) => (
                  <DropdownMenuItem key={idx} onClick={() => setDayOfWeek(String(idx))}>
                    {day}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </>
        )}

        {frequency === 'monthly' && (
          <>
            <span>on day</span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 transition-colors">
                  <span className="font-medium">{dayOfMonth}</span>
                  <ChevronDown className="w-3 h-3" />
                </button>
              </DropdownMenuTrigger>
              {/* MODIFIED: Added className */}
              <DropdownMenuContent align="start" className="max-h-60 overflow-y-auto bg-white">
                {Array.from({ length: 31 }, (_, i) => i + 1).map(day => (
                  <DropdownMenuItem key={day} onClick={() => setDayOfMonth(String(day))}>
                    {day}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </>
        )}

        {['hourly', 'daily', 'weekly', 'monthly'].includes(frequency) && (
          <>
            <span>at</span>
            {frequency === 'hourly' ? (
              <>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button className="flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 transition-colors">
                      <span className="font-medium">{minute.padStart(2, '0')}</span>
                      <ChevronDown className="w-3 h-3" />
                    </button>
                  </DropdownMenuTrigger>
                  {/* MODIFIED: Added className */}
                  <DropdownMenuContent align="start" className="max-h-60 overflow-y-auto bg-white">
                    {minuteOptions.map(min => (
                      <DropdownMenuItem key={min} onClick={() => setMinute(String(min))}>
                        {String(min).padStart(2, '0')}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
                <span>minutes past the hour</span>
              </>
            ) : (
              <>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button className="flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 transition-colors">
                      <span className="font-medium">{hour}</span>
                      <ChevronDown className="w-3 h-3" />
                    </button>
                  </DropdownMenuTrigger>
                  {/* MODIFIED: Added className */}
                  <DropdownMenuContent align="start" className="max-h-60 overflow-y-auto bg-white">
                    {Array.from({ length: 12 }, (_, i) => i + 1).map(hr => (
                      <DropdownMenuItem key={hr} onClick={() => setHour(String(hr))}>
                        {hr}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>

                <span>:</span>

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button className="flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 transition-colors">
                      <span className="font-medium">{minute.padStart(2, '0')}</span>
                      <ChevronDown className="w-3 h-3" />
                    </button>
                  </DropdownMenuTrigger>
                  {/* MODIFIED: Added className */}
                  <DropdownMenuContent align="start" className="max-h-60 overflow-y-auto bg-white">
                    {minuteOptions.map(min => (
                      <DropdownMenuItem key={min} onClick={() => setMinute(String(min))}>
                        {String(min).padStart(2, '0')}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button className="flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 transition-colors">
                      <span className="font-medium">{ampm}</span>
                      <ChevronDown className="w-3 h-3" />
                    </button>
                  </DropdownMenuTrigger>
                  {/* MODIFIED: Added className */}
                  <DropdownMenuContent align="start" className="bg-white">
                    <DropdownMenuItem onClick={() => setAmpm('AM')}>AM</DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setAmpm('PM')}>PM</DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </>
            )}
          </>
        )}
      </div>

      <div className="bg-gray-50 p-3 rounded-lg border">
        <p className="text-xs text-gray-600 mb-1">Cron Expression:</p>
        <code className="text-sm font-mono font-semibold">{value}</code>
      </div>
    </div>
  );
}

export function AssistantDashboard({ assistant, onBack, onOpenChat }: AssistantDashboardProps) {
  const [cronJobs, setCronJobs] = useState<CronJob[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showCreateCronDialog, setShowCreateCronDialog] = useState(false);
  const [showEditCronDialog, setShowEditCronDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showRunsDialog, setShowRunsDialog] = useState(false);
  const [showOutputDialog, setShowOutputDialog] = useState(false);
  const [selectedCron, setSelectedCron] = useState<CronJob | null>(null);
  const [cronRuns, setCronRuns] = useState<CronRun[]>([]);
  const [selectedOutput, setSelectedOutput] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'connections' | 'cron' | 'chat'>('connections');

  // Form states
  const [cronSchedule, setCronSchedule] = useState('0 0 * * *');
  const [cronInstructions, setCronInstructions] = useState('');
  const [cronFields, setCronFields] = useState<Record<string, string>>({});

  useEffect(() => {
    loadDashboard();
  }, [assistant.assistant_id]);

  const loadDashboard = async () => {
    setIsLoading(true);
    try {
      await loadCronJobs();
    } finally {
      setIsLoading(false);
    }
  };

  const loadCronJobs = async () => {
    try {
      const jobs = await listCrons(assistant.assistant_id);
      setCronJobs(jobs);
    } catch (error) {
      console.error('Error loading cron jobs:', error);
      toast.error('Failed to load cron jobs');
    }
  };

  const handleCreateCron = async () => {
    if (!cronSchedule) {
      toast.error('Schedule is required');
      return;
    }

    try {
      await createCron({
        assistant_id: assistant.assistant_id,
        schedule: cronSchedule,
        required_fields: cronFields,
        special_instructions: cronInstructions || undefined,
      });
      toast.success('Cron job created successfully');
      setShowCreateCronDialog(false);
      resetCronForm();
      loadCronJobs();
    } catch (error) {
      console.error('Error creating cron job:', error);
      toast.error('Failed to create cron job');
    }
  };

  const handleUpdateCron = async () => {
    if (!selectedCron) return;

    try {
      await updateCron(selectedCron.cron_id, {
        schedule: cronSchedule,
        required_fields: cronFields,
        special_instructions: cronInstructions || undefined,
        enabled: selectedCron.enabled,
      });
      toast.success('Cron job updated successfully');
      setShowEditCronDialog(false);
      resetCronForm();
      setSelectedCron(null);
      loadCronJobs();
    } catch (error) {
      console.error('Error updating cron job:', error);
      toast.error('Failed to update cron job');
    }
  };

  const handleToggleCron = async (cron: CronJob) => {
    try {
      await updateCron(cron.cron_id, { enabled: !cron.enabled });
      toast.success(`Cron job ${!cron.enabled ? 'enabled' : 'disabled'}`);
      loadCronJobs();
    } catch (error) {
      console.error('Error toggling cron job:', error);
      toast.error('Failed to toggle cron job');
    }
  };

  const handleDeleteCron = async () => {
    if (!selectedCron) return;

    try {
      await deleteCron(selectedCron.cron_id);
      toast.success('Cron job deleted successfully');
      setShowDeleteDialog(false);
      setSelectedCron(null);
      loadCronJobs();
    } catch (error) {
      console.error('Error deleting cron job:', error);
      toast.error('Failed to delete cron job');
    }
  };

  const handleRunNow = async (cron: CronJob) => {
    try {
      await runCronNow(cron.cron_id);
      toast.success('Cron job triggered successfully');
    } catch (error) {
      console.error('Error running cron job:', error);
      toast.error('Failed to run cron job');
    }
  };

  const handleViewRuns = async (cron: CronJob) => {
    setSelectedCron(cron);
    setShowRunsDialog(true);
    try {
      const runs = await listCronRuns(cron.cron_id);
      setCronRuns(runs);
    } catch (error) {
      console.error('Error loading cron runs:', error);
      toast.error('Failed to load cron runs');
    }
  };

  const handleViewOutput = (output: string) => {
    setSelectedOutput(output);
    setShowOutputDialog(true);
  };



  const openEditDialog = (cron: CronJob) => {
    setSelectedCron(cron);
    setCronSchedule(cron.schedule);
    setCronInstructions(cron.special_instructions || '');
    setCronFields(cron.required_fields || {});
    setShowEditCronDialog(true);
  };

  const openDeleteDialog = (cron: CronJob) => {
    setSelectedCron(cron);
    setShowDeleteDialog(true);
  };

  const resetCronForm = () => {
    setCronSchedule('0 0 * * *');
    setCronInstructions('');
    setCronFields({});
  };

  const getStatusBadge = (status: string) => {
    const statusConfig = {
      scheduled: { variant: 'secondary' as const, label: 'Scheduled', icon: Clock },
      running: { variant: 'default' as const, label: 'Running', icon: Loader2 },
      completed: { variant: 'default' as const, label: 'Completed', icon: CheckCircle },
      failed: { variant: 'destructive' as const, label: 'Failed', icon: XCircle },
    };

    const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.scheduled;
    const Icon = config.icon;

    return (
      <Badge variant={config.variant} className="gap-1">
        <Icon className="w-3 h-3" />
        {config.label}
      </Badge>
    );
  };

  // Ensure toolkits are connected before allowing navigation to chat or creating cron jobs.
  const ensureConnectionsOrPrompt = async (): Promise<boolean> => {
    // If no toolkits are required, allow immediately
    if (!assistant.tool_kits || assistant.tool_kits.length === 0) {
      return true;
    }

    // If we've already verified connections in this session, allow immediately
    try {
      const connectionsStatus = await checkToolkitConnections(assistant.tool_kits);

      // Check if all toolkits are connected
      const missingConnections = connectionsStatus.filter(status => status !== "connected");

      if (missingConnections.length > 0) {
        // Some toolkits are not connected, so prompt the user to connect
        setActiveTab('connections');
        toast.error('Please connect all required toolkits before continuing');
        return false;
      }

      return true;
    } catch (error) {
      console.error('Error checking toolkit connections:', error);
      toast.error('Could not verify toolkit connections. Please check connections.');
      setActiveTab('connections');
      return false;
    }
  };

  // Handler used when user clicks the Chat tab or the "Open Chat Interface" button
  const handleOpenChatClick = async () => {
    if (await ensureConnectionsOrPrompt()) {
      if (onOpenChat) onOpenChat();
    }
  };

  // Handler used for Create Cron Job button(s)
  const handleOpenCreateCron = async () => {
    if (await ensureConnectionsOrPrompt()) {
      setShowCreateCronDialog(true);
    }
  };

  const handleExportAssistant = async () => {
    try {
      const assistantData = await getAssistant(assistant.assistant_id);
      const jsonString = JSON.stringify(assistantData, null, 2);
      const blob = new Blob([jsonString], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${assistant.name.replace(/\s+/g, '_').toLowerCase()}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast.success('Assistant exported successfully!');
    } catch (error) {
      console.error('Export failed:', error);
      toast.error('Failed to export assistant.');
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-purple-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto p-6">
        {/* Header */}
        <div className="mb-6">
          <Button variant="ghost" onClick={onBack} className="mb-4">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Assistants
          </Button>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="mb-1">{assistant.name}</h1>
              <p className="text-gray-600">{assistant.description}</p>
            </div>
            <div className="flex flex-col items-end gap-2">
              <Badge variant="secondary">Dashboard</Badge>
              <Button variant="outline" size="sm" onClick={handleExportAssistant}>
                <Download className="w-4 h-4 mr-2" />
                Export
              </Button>
            </div>
          </div>
      </div>

        {/* Tabs */}
        <Tabs
          value={activeTab}
          onValueChange={async (v) => {
            // If navigating to chat, verify toolkit connections first
            if (v === 'chat') {
              if (await ensureConnectionsOrPrompt()) {
                setActiveTab('chat');
                if (onOpenChat) onOpenChat();
              }
            } else {
              setActiveTab(v as 'connections' | 'cron');
            }
          }}
          className="space-y-4"
        >
          <TabsList>
            <TabsTrigger value="connections" className="gap-2">
              <LinkIcon className="w-4 h-4" />
              Connections
            </TabsTrigger>
            <TabsTrigger value="cron" className="gap-2">
              <Clock className="w-4 h-4" />
              Cron Jobs
            </TabsTrigger>
            <TabsTrigger value="chat" className="gap-2">
              <MessageSquare className="w-4 h-4" />
              Chat
            </TabsTrigger>
          </TabsList>

          {/* Cron Jobs Tab */}
          <TabsContent value="cron" className="space-y-4">
            <div className="flex justify-between items-center">
              <h2>Scheduled Jobs</h2>
              <Button onClick={handleOpenCreateCron}>
                <Plus className="w-4 h-4 mr-2" />
                Create Cron Job
              </Button>
            </div>

            {cronJobs.length === 0 ? (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-12">
                  <Clock className="w-12 h-12 text-gray-300 mb-4" />
                  <h3 className="mb-2">No cron jobs yet</h3>
                  <p className="text-sm text-gray-600 mb-4">
                    Create a scheduled job to automate assistant runs
                  </p>
                  <Button onClick={handleOpenCreateCron}>
                    <Plus className="w-4 h-4 mr-2" />
                    Create First Cron Job
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4">
                {cronJobs.map((cron) => (
                  <Card key={cron.cron_id}>
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <CardTitle className="text-base">
                              Schedule: {cron.schedule}
                            </CardTitle>
                            {cron.enabled ? (
                              <Badge variant="default" className="bg-green-500">Enabled</Badge>
                            ) : (
                              <Badge variant="secondary">Disabled</Badge>
                            )}
                          </div>
                          {cron.special_instructions && (
                            <CardDescription>{cron.special_instructions}</CardDescription>
                          )}
                        </div>
                        <TooltipProvider>
                          <div className="flex gap-2">
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleViewRuns(cron)}
                                >
                                  <FileText className="w-4 h-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p>View run history</p>
                              </TooltipContent>
                            </Tooltip>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleRunNow(cron)}
                                >
                                  <Play className="w-4 h-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p>Run now</p>
                              </TooltipContent>
                            </Tooltip>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => openEditDialog(cron)}
                                >
                                  <Edit className="w-4 h-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p>Edit cron job</p>
                              </TooltipContent>
                            </Tooltip>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => openDeleteDialog(cron)}
                                >
                                  <Trash2 className="w-4 h-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p>Delete cron job</p>
                              </TooltipContent>
                            </Tooltip>
                          </div>
                        </TooltipProvider>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {Object.keys(cron.required_fields || {}).length > 0 && (
                          <div>
                            <p className="text-sm mb-1">Required Fields:</p>
                            <div className="flex flex-wrap gap-2">
                              {Object.entries(cron.required_fields || {}).map(([key, value]) => (
                                <Badge key={key} variant="outline">
                                  {key}: {String(value)}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}
                        <div className="flex items-center gap-2 pt-2">
                          <Switch
                            checked={cron.enabled}
                            onCheckedChange={() => handleToggleCron(cron)}
                          />
                          <Label className="text-sm">
                            {cron.enabled ? 'Enabled' : 'Disabled'}
                          </Label>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>

          {/* Connections Tab */}
          <TabsContent value="connections" className="space-y-4">
            <div className="flex justify-between items-center">
              <h2>Toolkit Connections</h2>
            </div>

            {!assistant.tool_kits || assistant.tool_kits.length === 0 ? (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-12">
                  <LinkIcon className="w-12 h-12 text-gray-300 mb-4" />
                  <h3 className="mb-2">No toolkits required</h3>
                  <p className="text-sm text-gray-600">
                    This assistant doesn't require any external toolkits
                  </p>
                </CardContent>
              </Card>
            ) : (
              <ToolkitConnectionManager
                toolkits={assistant.tool_kits}
                isEmbedded={true}
              />
            )}
          </TabsContent>

          {/* Chat Tab */}
          <TabsContent value="chat" className="space-y-4">
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <MessageSquare className="w-12 h-12 text-purple-600 mb-4" />
                <h3 className="mb-2">Start Chatting</h3>
                <p className="text-sm text-gray-600 mb-4 text-center">
                  Chat with {assistant.name} to test and interact with your agent
                </p>
                {onOpenChat && (
                  <Button onClick={handleOpenChatClick}>
                    <MessageSquare className="w-4 h-4 mr-2" />
                    Open Chat Interface
                  </Button>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      {/* Create Cron Dialog */}
      <Dialog open={showCreateCronDialog} onOpenChange={setShowCreateCronDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Create Cron Job</DialogTitle>
            <DialogDescription>
              Schedule automatic runs for this assistant
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Schedule</Label>
              <div className="mt-2 border rounded-lg p-4 bg-white">
                <CronScheduler value={cronSchedule} onChange={setCronSchedule} />
              </div>
            </div>

            <div>
              <Label htmlFor="instructions">Special Instructions (Optional)</Label>
              <Textarea
                id="instructions"
                placeholder="Enter any special instructions for this scheduled run..."
                value={cronInstructions}
                onChange={(e) => setCronInstructions(e.target.value)}
                rows={3}
              />
            </div>
            {assistant.required_fields && assistant.required_fields.length > 0 && (
              <div>
                <Label>Required Fields</Label>
                <div className="space-y-2 mt-2">
                  {assistant.required_fields.map((field) => (
                    <div key={field.name}>
                      <Label htmlFor={field.name} className="text-sm">
                        {field.name}
                      </Label>
                      <Input
                        id={field.name}
                        placeholder={field.description}
                        value={cronFields[field.name] || ''}
                        onChange={(e) =>
                          setCronFields({ ...cronFields, [field.name]: e.target.value })
                        }
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateCronDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateCron}>Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Cron Dialog */}
      <Dialog open={showEditCronDialog} onOpenChange={setShowEditCronDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Cron Job</DialogTitle>
            <DialogDescription>
              Update the schedule and settings for this cron job
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Schedule</Label>
              <div className="mt-2 border rounded-lg p-4 bg-white">
                <CronScheduler value={cronSchedule} onChange={setCronSchedule} />
              </div>
            </div>

            <div>
              <Label htmlFor="edit-instructions">Special Instructions</Label>
              <Textarea
                id="edit-instructions"
                placeholder="Enter any special instructions..."
                value={cronInstructions}
                onChange={(e) => setCronInstructions(e.target.value)}
                rows={3}
              />
            </div>
            {assistant.required_fields && assistant.required_fields.length > 0 && (
              <div>
                <Label>Required Fields</Label>
                <div className="space-y-2 mt-2">
                  {assistant.required_fields.map((field) => (
                    <div key={field.name}>
                      <Label htmlFor={`edit-${field.name}`} className="text-sm">
                        {field.name}
                      </Label>
                      <Input
                        id={`edit-${field.name}`}
                        placeholder={field.description}
                        value={cronFields[field.name] || ''}
                        onChange={(e) =>
                          setCronFields({ ...cronFields, [field.name]: e.target.value })
                        }
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditCronDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdateCron}>Update</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Cron Job</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this cron job? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteCron}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Cron Runs Dialog */}
      <Dialog open={showRunsDialog} onOpenChange={setShowRunsDialog}>
        <DialogContent className="sm:max-w-screen-xl max-h-[85vh]">
          <DialogHeader>
            <DialogTitle>Cron Job Runs</DialogTitle>
            <DialogDescription>
              History of all runs for this cron job
            </DialogDescription>
          </DialogHeader>
          <div className="border rounded-lg overflow-hidden">
            <ScrollArea className="h-[60vh]">
              {cronRuns.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12">
                  <FileText className="w-12 h-12 text-gray-300 mb-4" />
                  <p className="text-gray-600">No runs yet</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table className="table-fixed">
                    <TableHeader className="sticky top-0 bg-white z-10">
                      <TableRow>
                        <TableHead className="w-[140px]">Status</TableHead>
                        <TableHead className="w-[180px]">Scheduled At</TableHead>
                        <TableHead className="w-[180px]">Started At</TableHead>
                        <TableHead className="w-[180px]">Completed At</TableHead>
                        <TableHead className="w-[450px]">Output</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {cronRuns.map((run) => (
                        <TableRow key={run.cron_run_id}>
                          <TableCell>{getStatusBadge(run.status)}</TableCell>
                          <TableCell className="text-sm">
                            {run.scheduled_at
                              ? new Date(run.scheduled_at).toLocaleString('en-US', {
                                month: '2-digit',
                                day: '2-digit',
                                year: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit',
                                second: '2-digit',
                                hour12: true
                              })
                              : '-'}
                          </TableCell>
                          <TableCell className="text-sm">
                            {run.started_at
                              ? new Date(run.started_at).toLocaleString('en-US', {
                                month: '2-digit',
                                day: '2-digit',
                                year: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit',
                                second: '2-digit',
                                hour12: true
                              })
                              : '-'}
                          </TableCell>
                          <TableCell className="text-sm">
                            {run.completed_at
                              ? new Date(run.completed_at).toLocaleString('en-US', {
                                month: '2-digit',
                                day: '2-digit',
                                year: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit',
                                second: '2-digit',
                                hour12: true
                              })
                              : '-'}
                          </TableCell>
                          <TableCell className="text-sm whitespace-normal align-top">
                            {run.output ? (
                              <div className="flex items-start gap-2">
                                <p className="line-clamp-2 flex-1">{run.output}</p>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleViewOutput(run.output || '')}
                                  className="shrink-0"
                                >
                                  <Maximize2 className="w-4 h-4" />
                                </Button>
                              </div>
                            ) : (
                              '-'
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </ScrollArea>
          </div>
        </DialogContent>
      </Dialog>

      {/* Output Viewer Dialog */}
      <Dialog open={showOutputDialog} onOpenChange={setShowOutputDialog}>
        <DialogContent className="w-[90vw] max-w-[1200px] max-h-[90vh]">
          <DialogHeader>
            <DialogTitle>Run Output</DialogTitle>
            <DialogDescription>
              Complete output from the cron job run
            </DialogDescription>
          </DialogHeader>
          <ScrollArea className="h-[70vh] border rounded-lg p-4">
            <div className="prose prose-sm max-w-none dark:prose-invert">
              <ReactMarkdown>{selectedOutput || 'No output available'}</ReactMarkdown>
            </div>
          </ScrollArea>
          <DialogFooter>
            <Button onClick={() => setShowOutputDialog(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}