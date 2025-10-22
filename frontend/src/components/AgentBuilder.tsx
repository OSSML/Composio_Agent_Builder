import { useState } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Card } from './ui/card';
import { Loader2, Sparkles } from 'lucide-react';
import { createThread, createRun, pollRun, getThreadHistory, createAssistant, RequiredField } from '../lib/api';

interface AgentBuilderProps {
  onAgentCreated: (assistantId: string) => void;
}

interface AgentConfig {
  system_prompt: string;
  tool_kits: string[];
  tools: string[];
  required_fields: RequiredField[];
}

export function AgentBuilder({ onAgentCreated }: AgentBuilderProps) {
  const [taskName, setTaskName] = useState('');
  const [taskDescription, setTaskDescription] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [agentConfig, setAgentConfig] = useState<AgentConfig | null>(null);
  const [showPromptEditor, setShowPromptEditor] = useState(false);
  const [status, setStatus] = useState('');

  const handleGenerateAgent = async () => {
    if (!taskName.trim() || !taskDescription.trim()) {
      alert('Please provide both task name and description');
      return;
    }

    setIsGenerating(true);
    setStatus('Finding agent builder...');

    try {
      // Step 1: Get agent_builder assistant (hardcoded for now, or fetch from API)
      const agentBuilderId = 'a38fd80f-fc84-5947-b925-bb8cbac617da'; // You might want to fetch this

      // Step 2: Create thread for agent_builder
      setStatus('Creating planning session...');
      const thread = await createThread('agent_builder', agentBuilderId);

      // Step 3: Create run with task name and description
      setStatus('Generating system prompt...');
      const input = {
        messages: [
          {
            type: 'human',
            content: [
              {
                type: 'text',
                text: `${taskName} – ${taskDescription}`
              }
            ]
          }
        ]
      };

      const run = await createRun(thread.thread_id, agentBuilderId, input);

      // Step 4: Poll until completion
      await pollRun(thread.thread_id, run.run_id, (currentRun) => {
        setStatus(`Status: ${currentRun.status}...`);
      });

      // Step 5: Get thread history
      setStatus('Retrieving generated prompt...');
      const history = await getThreadHistory(thread.thread_id, 1);

      // Extract the last AI message
      if (history.length > 0 && history[0].values.messages) {
        const messages = history[0].values.messages;
        const lastAiMessage = messages.reverse().find(m => m.type === 'ai');

        if (lastAiMessage) {
          const content = typeof lastAiMessage.content === 'string'
            ? lastAiMessage.content
            : lastAiMessage.content.map(c => c.text || '').join('');

          // Parse JSON from the content
          try {
            const parsed = JSON.parse(content);
            setAgentConfig({
              system_prompt: parsed.system_prompt || '',
              tools: parsed.tools || [],
              tool_kits: parsed.tool_kits || [],
              required_fields: parsed.required_fields || []
            });
            setShowPromptEditor(true);
            setStatus('');
          } catch (parseError) {
            console.error('Failed to parse agent config:', parseError);
            setStatus('Error: Invalid response format from agent builder');
          }
        }
      }

    } catch (error) {
      console.error('Error generating agent:', error);
      setStatus('Error: ' + (error as Error).message);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCreateAgent = async () => {
    if (!agentConfig || !agentConfig.system_prompt.trim()) {
      alert('System prompt cannot be empty');
      return;
    }

    setIsGenerating(true);
    setStatus('Creating agent...');

    try {
      // Create the assistant with the system prompt, toolkits, and required fields
      const assistant = await createAssistant({
        graph_id: 'agent_template',
        name: taskName,
        description: taskDescription,
        context: {
          system_prompt: agentConfig.system_prompt,
          tools: agentConfig.tools,
        },
        tool_kits: agentConfig.tool_kits,
        required_fields: agentConfig.required_fields
      });

      setStatus('Agent created successfully!');
      setTimeout(() => {
        onAgentCreated(assistant.assistant_id);
      }, 500);

    } catch (error) {
      console.error('Error creating agent:', error);
      setStatus('Error: ' + (error as Error).message);
      setIsGenerating(false);
    }
  };

  if (showPromptEditor) {
    return (
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        <div className="flex items-center gap-3 mb-6">
          <Sparkles className="w-8 h-8 text-purple-500" />
          <div>
            <h2>Review Generated Plan</h2>
            <p className="text-sm text-gray-600">Edit the system prompt if needed, then create your agent</p>
          </div>
        </div>

        <Card className="p-6 space-y-4">
          <div>
            <Label htmlFor="agent-name">Agent Name</Label>
            <Input
              id="agent-name"
              value={taskName}
              onChange={(e) => setTaskName(e.target.value)}
              disabled={isGenerating}
              className="mt-1"
            />
          </div>

          <div>
            <Label htmlFor="agent-description">Description</Label>
            <Input
              id="agent-description"
              value={taskDescription}
              onChange={(e) => setTaskDescription(e.target.value)}
              disabled={isGenerating}
              className="mt-1"
            />
          </div>

          <div>
            <Label htmlFor="system-prompt">System Prompt</Label>
            <Textarea
              id="system-prompt"
              value={agentConfig?.system_prompt || ''}
              onChange={(e) => setAgentConfig(prev => prev ? { ...prev, system_prompt: e.target.value } : null)}
              disabled={isGenerating}
              rows={12}
              className="mt-1 font-mono text-sm"
            />
          </div>

          <div>
            <Label>Toolkits</Label>
            <div className="mt-1 p-3 bg-gray-50 rounded text-sm">
              {agentConfig?.tool_kits && agentConfig.tool_kits.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {agentConfig.tool_kits.map((toolkit, idx) => (
                    <span key={idx} className="px-2 py-1 bg-purple-100 text-purple-700 rounded">
                      {toolkit}
                    </span>
                  ))}
                </div>
              ) : (
                <span className="text-gray-500">No toolkits required</span>
              )}
            </div>
          </div>

          <div>
            <Label>Required Fields</Label>
            <div className="mt-1 p-3 bg-gray-50 rounded text-sm space-y-2">
              {agentConfig?.required_fields && agentConfig.required_fields.length > 0 ? (
                agentConfig.required_fields.map((field, idx) => (
                  <div key={idx} className="flex items-start gap-2">
                    <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">{field.type}</span>
                    <div className="flex-1">
                      <span className="block">{field.name}</span>
                      <span className="text-xs text-gray-500">{field.description}</span>
                    </div>
                  </div>
                ))
              ) : (
                <span className="text-gray-500">No required fields</span>
              )}
            </div>
          </div>

          {status && (
            <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded">
              {status}
            </div>
          )}

          <div className="flex gap-3">
            <Button
              onClick={handleCreateAgent}
              disabled={isGenerating}
              className="flex-1"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Creating Agent...
                </>
              ) : (
                'Create Agent'
              )}
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setShowPromptEditor(false);
                setAgentConfig(null);
              }}
              disabled={isGenerating}
            >
              Start Over
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <div className="flex items-center gap-3 mb-6">
        <Sparkles className="w-8 h-8 text-purple-500" />
        <div>
          <h1>Composio Agent Builder</h1>
          <p className="text-sm text-gray-600">Describe your task and we'll generate a custom AI agent</p>
        </div>
      </div>

      <Card className="p-6 space-y-6">
        <div>
          <Label htmlFor="task-name">Task Name</Label>
          <Input
            id="task-name"
            placeholder="e.g., AI Engineer Workspace Orchestrator"
            value={taskName}
            onChange={(e) => setTaskName(e.target.value)}
            disabled={isGenerating}
            className="mt-1"
          />
        </div>

        <div>
          <Label htmlFor="task-description">Task Description</Label>
          <Textarea
            id="task-description"
            placeholder="e.g., Compile release notes by pulling GitHub PRs, drafting in Docs, and posting to Discord."
            value={taskDescription}
            onChange={(e) => setTaskDescription(e.target.value)}
            disabled={isGenerating}
            rows={4}
            className="mt-1"
          />
        </div>

        {status && (
          <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded">
            {status}
          </div>
        )}

        <Button
          onClick={handleGenerateAgent}
          disabled={isGenerating || !taskName.trim() || !taskDescription.trim()}
          className="w-full"
        >
          {isGenerating ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Generating Agent...
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4 mr-2" />
              Generate Agent
            </>
          )}
        </Button>
      </Card>
    </div>
  );
}
