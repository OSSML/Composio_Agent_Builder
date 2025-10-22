import { useEffect, useState, useRef } from 'react';
import { Assistant, listAssistants, createAssistant } from '../lib/api';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Bot, Plus, Loader2, Upload } from 'lucide-react';
import { Badge } from './ui/badge';
import { toast } from 'sonner';

interface AssistantsListProps {
  onSelectAssistant: (assistant: Assistant) => void;
  onCreateNew: () => void;
}

export function AssistantsList({ onSelectAssistant, onCreateNew }: AssistantsListProps) {
  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [loading, setLoading] = useState(true);
  const [isImporting, setIsImporting] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadAssistants();
  }, []);

  const loadAssistants = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await listAssistants();
      // Filter out the builder assistants and default assistants
      const userAssistants = data.filter(a => {
        // Only show agent_template assistants
        if (a.graph_id !== 'agent_template') return false;
        // Filter out default assistants (those with "Default assistant for graph" in description)
        if (a.description && a.description.includes('Default assistant for graph')) return false;
        return true;
      });
      setAssistants(userAssistants);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsImporting(true);
    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const fileContent = e.target?.result;
        if (typeof fileContent !== 'string') {
          throw new Error('Could not read file content.');
        }
        const data = JSON.parse(fileContent);

        // Remove read-only fields before sending to create API
        const { assistant_id, created_at, updated_at, ...createData } = data;

        if (!createData.graph_id || !createData.name) {
            throw new Error('Imported file is missing required fields like name or graph_id.');
        }

        await createAssistant(createData);
        toast.success(`Successfully imported assistant: ${createData.name}`);
        await loadAssistants(); // Refresh the list
      } catch (err) {
        toast.error(`Import failed: ${(err as Error).message}`);
      } finally {
        setIsImporting(false);
        // Reset input to allow re-uploading the same file
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      }
    };
    reader.onerror = () => {
      setIsImporting(false);
      toast.error('Error reading the selected file.');
    };
    reader.readAsText(file);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto p-6">
        <Card className="p-6 text-center">
          <p className="text-red-600">Error loading assistants: {error}</p>
          <Button onClick={loadAssistants} className="mt-4">
            Retry
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="mb-1">Composio Agent Builder</h1>
          <p className="text-sm text-gray-600">Manage and chat with your AI agents</p>
        </div>
        <div className="flex items-center gap-2">
            <Button variant="outline" onClick={handleImportClick} disabled={isImporting}>
                {isImporting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Upload className="w-4 h-4 mr-2" />}
                Import Agent
            </Button>
            <Button onClick={onCreateNew}>
                <Plus className="w-4 h-4 mr-2" />
                Create New Agent
            </Button>
            <input
                type="file"
                ref={fileInputRef}
                style={{ display: 'none' }}
                className="hidden"
                accept="application/json"
                onChange={handleFileChange}
            />
        </div>
      </div>

      {assistants.length === 0 ? (
        <Card className="p-12 text-center">
          <Bot className="w-16 h-16 mx-auto mb-4 text-gray-300" />
          <h3 className="mb-2">No assistants yet</h3>
          <p className="text-sm text-gray-600 mb-4">
            Create your first AI agent to get started
          </p>
          <Button onClick={onCreateNew}>
            <Plus className="w-4 h-4 mr-2" />
            Create Your First Agent
          </Button>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {assistants.map((assistant) => (
            <Card
              key={assistant.assistant_id}
              className="p-6 hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => onSelectAssistant(assistant)}
            >
              <div className="flex items-start gap-3">
                <div className="p-2 bg-purple-100 rounded-lg">
                  <Bot className="w-5 h-5 text-purple-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="truncate">{assistant.name}</h3>
                  <p className="text-sm text-gray-600 line-clamp-2 mt-1">
                    {assistant.description || 'No description'}
                  </p>
                  <div className="flex items-center gap-2 mt-3">
                    <Badge variant="secondary" className="text-xs">
                      {assistant.graph_id}
                    </Badge>
                    <span className="text-xs text-gray-500">
                      {new Date(assistant.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
