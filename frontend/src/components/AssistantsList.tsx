import { useEffect, useState } from 'react';
import { Assistant, listAssistants } from '../lib/api';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Bot, Plus, Loader2 } from 'lucide-react';
import { Badge } from './ui/badge';

interface AssistantsListProps {
  onSelectAssistant: (assistant: Assistant) => void;
  onCreateNew: () => void;
}

export function AssistantsList({ onSelectAssistant, onCreateNew }: AssistantsListProps) {
  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

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
        <Button onClick={onCreateNew}>
          <Plus className="w-4 h-4 mr-2" />
          Create New Agent
        </Button>
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
