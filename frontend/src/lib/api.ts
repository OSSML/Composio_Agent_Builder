// API base URL - update this to your backend URL
const API_BASE_URL = 'http://localhost:8000';

export interface RequiredField {
  name: string;
  description: string;
  type: string;
  required: boolean;
}

export interface Assistant {
  assistant_id: string;
  name: string;
  description: string | null;
  config: Record<string, any>;
  context: Record<string, any>;
  tool_kits?: string[];
  required_fields?: RequiredField[];
  graph_id: string;
  created_at: string;
  updated_at: string;
}

export interface Thread {
  assistant_id: string;
  thread_id: string;
  status: string;
  metadata: Record<string, any>;
  created_at: string;
}

export interface Run {
  run_id: string;
  thread_id: string;
  assistant_id: string;
  status: string;
  input: Record<string, any>;
  output: Record<string, any> | null;
  error_message: string | null;
  config: Record<string, any>;
  context: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface Message {
  type: 'human' | 'ai' | 'tool';
  content: string | Array<{ type: string; text: string }>;
  id?: string;
  additional_kwargs?: any;
  response_metadata?: any;
}

export interface ThreadState {
  values: {
    messages: Message[];
  };
  next: string[];
  tasks: any[];
  interrupts: any[];
  metadata: Record<string, any>;
  created_at: string;
  checkpoint_id: string;
  parent_checkpoint_id: string;
}

// List all assistants
export async function listAssistants(): Promise<Assistant[]> {
  const response = await fetch(`${API_BASE_URL}/api/assistants`, {
    headers: { 'Accept': 'application/json' }
  });
  if (!response.ok) throw new Error('Failed to fetch assistants');
  return response.json();
}

// Create a new assistant
export async function createAssistant(data: {
  graph_id: string;
  name?: string;
  description?: string;
  context?: Record<string, any>;
  tool_kits?: string[];
  tools?: string[];
  required_fields?: RequiredField[];
}): Promise<Assistant> {
  const response = await fetch(`${API_BASE_URL}/api/assistants`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    },
    body: JSON.stringify(data)
  });
  if (!response.ok) throw new Error('Failed to create assistant');
  return response.json();
}

// Get a single assistant's details
export async function getAssistant(assistant_id: string): Promise<Assistant> {
  const response = await fetch(`${API_BASE_URL}/api/assistants/${assistant_id}`, {
    headers: { 'Accept': 'application/json' }
  });
  if (!response.ok) throw new Error('Failed to fetch assistant');
  return response.json();
}

// Create a new chat thread
export async function createThread(graph_id: string, assistant_id: string): Promise<Thread> {
  const response = await fetch(`${API_BASE_URL}/api/chat/new`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    },
    body: JSON.stringify({ graph_id, assistant_id })
  });
  if (!response.ok) throw new Error('Failed to create thread');
  return response.json();
}

// Search threads
export async function searchThreads(metadata?: Record<string, any>): Promise<{
  threads: Thread[];
  total: number;
  limit: number;
  offset: number;
}> {
  const response = await fetch(`${API_BASE_URL}/api/chat/search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    },
    body: JSON.stringify({ metadata })
  });
  if (!response.ok) throw new Error('Failed to search threads');
  return response.json();
}

// Create a run
export async function createRun(
  thread_id: string,
  assistant_id: string,
  input: Record<string, any>
): Promise<Run> {
  const response = await fetch(`${API_BASE_URL}/api/chat/${thread_id}/runs`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    },
    body: JSON.stringify({ assistant_id, input })
  });
  if (!response.ok) throw new Error('Failed to create run');
  return response.json();
}

// Get run status
export async function getRun(thread_id: string, run_id: string): Promise<Run> {
  const response = await fetch(`${API_BASE_URL}/api/chat/${thread_id}/runs/${run_id}`, {
    headers: { 'Accept': 'application/json' }
  });
  if (!response.ok) throw new Error('Failed to fetch run');
  return response.json();
}

// Get thread history
export async function getThreadHistory(thread_id: string, limit: number = 1): Promise<ThreadState[]> {
  const response = await fetch(`${API_BASE_URL}/api/chat/${thread_id}/history`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    },
    body: JSON.stringify({ limit })
  });
  if (!response.ok) throw new Error('Failed to fetch thread history');
  return response.json();
}

// Stream a run (Server-Sent Events)
export async function streamRun(
  thread_id: string,
  assistant_id: string,
  input: Record<string, any>,
  onMessage: (event: { type: string; data: any }) => void,
  onComplete: () => void,
  onError: (error: Error) => void
): Promise<void> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/threads/${thread_id}/runs/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
      },
      body: JSON.stringify({ assistant_id, input })
    });

    if (!response.ok) throw new Error('Failed to stream run');

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) throw new Error('No reader available');

    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('event:')) {
          const eventType = line.substring(6).trim();
          continue;
        }

        if (line.startsWith('data:')) {
          const data = line.substring(5).trim();

          try {
            const parsed = JSON.parse(data);

            // Determine event type from the data
            if (parsed.status === 'completed') {
              onMessage({ type: 'end', data: parsed });
              onComplete();
            } else if (Array.isArray(parsed)) {
              onMessage({ type: 'messages', data: parsed });
            } else if (parsed.messages) {
              onMessage({ type: 'values', data: parsed });
            }
          } catch (e) {
            // Skip invalid JSON
          }
        }
      }
    }
  } catch (error) {
    onError(error as Error);
  }
}

// Poll run until completion
export async function pollRun(
  thread_id: string,
  run_id: string,
  onProgress?: (run: Run) => void
): Promise<Run> {
  return new Promise((resolve, reject) => {
    const interval = setInterval(async () => {
      try {
        const run = await getRun(thread_id, run_id);

        if (onProgress) onProgress(run);

        if (run.status === 'completed') {
          clearInterval(interval);
          resolve(run);
        } else if (run.status === 'error' || run.status === 'failed') {
          clearInterval(interval);
          reject(new Error(run.error_message || 'Run failed'));
        }
      } catch (error) {
        clearInterval(interval);
        reject(error);
      }
    }, 2000); // Poll every 2 seconds
  });
}

// Check toolkit connections
export async function checkToolkitConnections(toolkits: string[]): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/api/tools/connect`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    },
    body: JSON.stringify({ tools: toolkits })
  });
  if (!response.ok) throw new Error('Failed to check toolkit connections');
  return response.json();
}

// Disconnect a toolkit
export async function disconnectToolkit(toolkit: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/api/tools/disconnect`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    },
    body: JSON.stringify({ tool: toolkit })
  });
  if (!response.ok) throw new Error('Failed to disconnect toolkit');
  return response.json();
}

// Cron job types
export interface CronJob {
  cron_id: string;
  assistant_id: string;
  schedule: string;
  required_fields: Record<string, any>;
  special_instructions?: string | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface CronRun {
  cron_run_id: string;
  cron_id: string;
  status: string;
  output?: string | null;
  scheduled_at: string | null;
  started_at: string | null;
  completed_at?: string | null;
}

// Create a cron job
export async function createCron(data: {
  assistant_id: string;
  schedule: string;
  required_fields?: Record<string, any>;
  special_instructions?: string;
}): Promise<CronJob> {
  const response = await fetch(`${API_BASE_URL}/api/cron`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    },
    body: JSON.stringify(data)
  });
  if (!response.ok) throw new Error('Failed to create cron job');
  return response.json();
}

// List cron jobs for an assistant
export async function listCrons(assistant_id?: string): Promise<CronJob[]> {
  const url = assistant_id
    ? `${API_BASE_URL}/api/cron?assistant_id=${assistant_id}`
    : `${API_BASE_URL}/api/cron`;
  const response = await fetch(url, {
    headers: { 'Accept': 'application/json' }
  });
  if (!response.ok) throw new Error('Failed to fetch cron jobs');
  return response.json();
}

// Get a specific cron job
export async function getCron(cron_id: string): Promise<CronJob> {
  const response = await fetch(`${API_BASE_URL}/api/cron/${cron_id}`, {
    headers: { 'Accept': 'application/json' }
  });
  if (!response.ok) throw new Error('Failed to fetch cron job');
  return response.json();
}

// Update a cron job
export async function updateCron(
  cron_id: string,
  data: {
    schedule?: string;
    required_fields?: Record<string, any>;
    special_instructions?: string;
    enabled?: boolean;
  }
): Promise<CronJob> {
  const response = await fetch(`${API_BASE_URL}/api/cron/${cron_id}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    },
    body: JSON.stringify(data)
  });
  if (!response.ok) throw new Error('Failed to update cron job');
  return response.json();
}

// Delete a cron job
export async function deleteCron(cron_id: string): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/cron/${cron_id}`, {
    method: 'DELETE',
    headers: { 'Accept': 'application/json' }
  });
  if (!response.ok) throw new Error('Failed to delete cron job');
  return response.json();
}

// Run a cron job immediately
export async function runCronNow(cron_id: string): Promise<CronRun> {
  const response = await fetch(`${API_BASE_URL}/api/cron/${cron_id}/run`, {
    method: 'POST',
    headers: { 'Accept': 'application/json' }
  });
  if (!response.ok) throw new Error('Failed to run cron job');
  return response.json();
}

// List cron runs for a specific cron job
export async function listCronRuns(cron_id: string): Promise<CronRun[]> {
  const response = await fetch(`${API_BASE_URL}/api/cron/${cron_id}/runs`, {
    headers: { 'Accept': 'application/json' }
  });
  if (!response.ok) throw new Error('Failed to fetch cron runs');
  return response.json();
}
