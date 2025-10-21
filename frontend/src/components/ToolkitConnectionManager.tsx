import { useState, useEffect } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Loader2, CheckCircle2, XCircle, ExternalLink, Unplug } from 'lucide-react';
import { checkToolkitConnections, disconnectToolkit } from '../lib/api';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from './ui/dialog';

interface ToolkitConnectionManagerProps {
  toolkits: string[];
  isEmbedded?: boolean;
}

interface ToolkitStatus {
  name: string;
  connected: boolean;
  connectionUrl?: string;
}

export function ToolkitConnectionManager({ toolkits, isEmbedded = false }: ToolkitConnectionManagerProps) {
  const [toolkitStatuses, setToolkitStatuses] = useState<ToolkitStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);
  const [showDialog, setShowDialog] = useState(!isEmbedded);

  useEffect(() => {
    checkConnections();
  }, [toolkits]);

  const checkConnections = async () => {
    setLoading(true);
    try {
      const results = await checkToolkitConnections(toolkits);

      const statuses: ToolkitStatus[] = toolkits.map((toolkit, index) => {
        const result = results[index];
        return {
          name: toolkit,
          connected: result === 'connected',
          connectionUrl: result !== 'connected' ? result : undefined
        };
      });

      setToolkitStatuses(statuses);

      // If all are connected, auto-proceed (only for non-embedded mode)
      if (statuses.every(s => s.connected) && !isEmbedded) {
        setTimeout(() => {
          setShowDialog(false);
        }, 1000);
      }
    } catch (error) {
      console.error('Error checking toolkit connections:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async (toolkit: string) => {
    setDisconnecting(toolkit);
    try {
      const reconnectUrl = await disconnectToolkit(toolkit);

      // Update the status to show disconnected with new connection URL
      setToolkitStatuses(prev =>
        prev.map(status =>
          status.name === toolkit
            ? { ...status, connected: false, connectionUrl: reconnectUrl }
            : status
        )
      );
    } catch (error) {
      console.error('Error disconnecting toolkit:', error);
    } finally {
      setDisconnecting(null);
    }
  };

  const allConnected = toolkitStatuses.every(s => s.connected);

  const content = (
    <>
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
        </div>
      ) : (
        <div className="space-y-4">
          {toolkitStatuses.map((status) => (
            <Card key={status.name} className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {status.connected ? (
                    <CheckCircle2 className="w-5 h-5 text-green-600" />
                  ) : (
                    <XCircle className="w-5 h-5 text-red-600" />
                  )}
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="uppercase tracking-wide">{status.name}</span>
                      <Badge variant={status.connected ? 'default' : 'destructive'}>
                        {status.connected ? 'Connected' : 'Not Connected'}
                      </Badge>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {status.connected ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDisconnect(status.name)}
                      disabled={disconnecting === status.name}
                    >
                      {disconnecting === status.name ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Disconnecting...
                        </>
                      ) : (
                        <>
                          <Unplug className="w-4 h-4 mr-2" />
                          Disconnect
                        </>
                      )}
                    </Button>
                  ) : status.connectionUrl ? (
                    <Button
                      size="sm"
                      onClick={() => window.open(status.connectionUrl, '_blank')}
                    >
                      <ExternalLink className="w-4 h-4 mr-2" />
                      Connect
                    </Button>
                  ) : null}
                </div>
              </div>
            </Card>
          ))}

          {!isEmbedded && (
            <div className="flex items-center justify-between pt-4 border-t">
              <p className="text-sm text-gray-600">
                {allConnected
                  ? 'All toolkits connected! You can now use this agent.'
                  : 'Please connect all required toolkits to continue.'}
              </p>
              {allConnected && (
                <Button onClick={() => {
                  setShowDialog(false);
                }}>
                  Continue
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </>
  );

  if (isEmbedded) {
    return <div>{content}</div>;
  }

  return (
    <Dialog open={showDialog} onOpenChange={setShowDialog}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Toolkit Connections Required</DialogTitle>
          <DialogDescription>
            This agent requires the following toolkits to be connected. Please connect any missing toolkits to continue.
          </DialogDescription>
        </DialogHeader>
        {content}
      </DialogContent>
    </Dialog>
  );
}
