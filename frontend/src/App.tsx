import { useState } from 'react';
import { AgentBuilder } from './components/AgentBuilder';
import { AssistantsList } from './components/AssistantsList';
import { ChatInterface } from './components/ChatInterface';
import { AssistantDashboard } from './components/AssistantDashboard';
import { Assistant } from './lib/api';
import { Toaster } from './components/ui/sonner';

type View = 'list' | 'builder' | 'chat' | 'dashboard';

export default function App() {
  const [currentView, setCurrentView] = useState<View>('list');
  const [selectedAssistant, setSelectedAssistant] = useState<Assistant | null>(null);

  const handleAgentCreated = (assistantId: string) => {
    // Redirect to assistants list after creation
    setCurrentView('list');
  };

  const handleSelectAssistant = (assistant: Assistant) => {
    setSelectedAssistant(assistant);
    setCurrentView('dashboard');
  };

  const handleBackToList = () => {
    setSelectedAssistant(null);
    setCurrentView('list');
  };

  const handleOpenDashboard = () => {
    setCurrentView('dashboard');
  };

  const handleOpenChat = () => {
    setCurrentView('chat');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {currentView === 'builder' && (
        <AgentBuilder
            onAgentCreated={handleAgentCreated}
            onBack={handleBackToList}
        />
      )}

      {currentView === 'list' && (
        <AssistantsList
          onSelectAssistant={handleSelectAssistant}
          onCreateNew={() => setCurrentView('builder')}
        />
      )}

      {currentView === 'chat' && selectedAssistant && (
        <ChatInterface
          assistant={selectedAssistant}
          onBack={handleOpenDashboard} // changed: go back to dashboard
        />
      )}

      {currentView === 'dashboard' && selectedAssistant && (
        <AssistantDashboard
          assistant={selectedAssistant}
          onBack={handleBackToList}
          onOpenChat={handleOpenChat}
        />
      )}

      <Toaster />
    </div>
  );
}
