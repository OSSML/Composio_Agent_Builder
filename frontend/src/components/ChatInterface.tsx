import { useState, useEffect, useRef } from 'react';
import { Assistant, Thread, Message, createThread, streamRun, getThreadHistory, searchThreads } from '../lib/api'; // removed checkToolkitConnections
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Card } from './ui/card';
import { ArrowLeft, Send, Plus, MessageSquare, Loader2, Bot, User, ChevronLeft, ChevronRight, Settings } from 'lucide-react';
import { ScrollArea } from './ui/scroll-area';
import { cn } from './ui/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
// removed ToolkitConnectionManager import
import { toast } from 'sonner';

interface ChatInterfaceProps {
  assistant: Assistant;
  onBack: () => void;
  onOpenDashboard?: () => void;
}

export function ChatInterface({ assistant, onBack, onOpenDashboard }: ChatInterfaceProps) {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [selectedThread, setSelectedThread] = useState<Thread | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [toolCall, setToolCall] = useState<{ name: string } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Check if assistant requires toolkits
  const requiresToolkits = assistant.tool_kits && assistant.tool_kits.length > 0;

  useEffect(() => {
    // Load threads when assistant changes. Connection checks are handled in Dashboard.
    loadThreads();
  }, [assistant.assistant_id]);

  useEffect(() => {
    if (selectedThread) {
      // Clear current messages before loading new thread
      setMessages([]);
      loadMessages();
    }
  }, [selectedThread]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, toolCall]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadThreads = async () => {
    setIsLoading(true);
    try {
      const result = await searchThreads({ graph_id: assistant.graph_id });
      // Filter threads for this specific assistant
      const assistantThreads = result.threads.filter(t => t.assistant_id === assistant.assistant_id);
      setThreads(assistantThreads);

      // Auto-select first thread if exists
      if (assistantThreads.length > 0 && !selectedThread) {
        setSelectedThread(assistantThreads[0]);
      }
    } catch (error) {
      console.error('Error loading threads:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadMessages = async () => {
    if (!selectedThread) return;

    setIsLoading(true);
    try {
      const history = await getThreadHistory(selectedThread.thread_id, 1);

      const allMessages: Message[] = [];
      history.forEach(state => {
        if (state.values.messages) {
          const filteredMessages = state.values.messages.filter((msg: Message) => {
            if (msg.type === 'human') return true;
            if (msg.type === 'ai') {
              const hasContent = msg.content &&
                (typeof msg.content === 'string' ? msg.content.trim().length > 0 : (Array.isArray(msg.content) && msg.content.length > 0));
              return hasContent;
            }
            return false;
          });
          allMessages.push(...filteredMessages);
        }
      });

      const groupedMessages: Message[] = [];
      for (const message of allMessages) {
        const lastMessage = groupedMessages[groupedMessages.length - 1];
        if (lastMessage && lastMessage.type === 'ai' && message.type === 'ai') {
          const formatContent = (content: any) => Array.isArray(content) ? content : [{ type: 'text', text: String(content) }];
          const lastContent = formatContent(lastMessage.content);
          const currentContent = formatContent(message.content);
          lastMessage.content = [...lastContent, ...currentContent];
        } else {
          groupedMessages.push({ ...message });
        }
      }

      setMessages(groupedMessages);
    } catch (error) {
      console.error('Error loading messages:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateNewThread = async () => {
    try {
      const newThread = await createThread(assistant.graph_id, assistant.assistant_id);
      setThreads([newThread, ...threads]);
      setSelectedThread(newThread);
      setMessages([]);
    } catch (error) {
      console.error('Error creating thread:', error);
      toast.error('Failed to create new chat');
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || !selectedThread || isSending) return;

    const userMessage: Message = {
      type: 'human',
      content: [{ type: 'text', text: inputMessage }],
      id: Date.now().toString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsSending(true);
    setToolCall(null);

    let aiMessageContent = '';

    try {
      const input = {
        messages: [
          {
            type: 'human',
            content: [{ type: 'text', text: inputMessage }]
          }
        ]
      };

      await streamRun(
        selectedThread.thread_id,
        assistant.assistant_id,
        input,
        (event) => {
          if (event.type === 'messages' && Array.isArray(event.data)) {
            event.data.forEach((msg: any) => {
              if (msg.type === 'AIMessageChunk') {
                if (msg.tool_call_chunks && msg.tool_call_chunks.length > 0) {
                  const toolChunk = msg.tool_call_chunks[0];
                  if (toolChunk.name) {
                    setToolCall({ name: toolChunk.name });
                  }
                }
                if (msg.content) {
                  setToolCall(null);
                  aiMessageContent += msg.content;
                }
              }
            });

            if (aiMessageContent) {
              setMessages(prev => {
                const filtered = prev.filter(m => m.id !== 'streaming');
                return [
                  ...filtered,
                  {
                    type: 'ai',
                    content: aiMessageContent,
                    id: 'streaming'
                  }
                ];
              });
            }
          }
        },
        () => {
          setMessages(prev => {
            const filtered = prev.filter(m => m.id !== 'streaming');
            return [
              ...filtered,
              {
                type: 'ai',
                content: aiMessageContent,
                id: Date.now().toString()
              }
            ];
          });
          setIsSending(false);
          setToolCall(null);
        },
        (error) => {
          console.error('Streaming error:', error);
          setIsSending(false);
          setToolCall(null);
        }
      );
    } catch (error) {
      console.error('Error sending message:', error);
      setIsSending(false);
      setToolCall(null);
    }
  };

  const formatMessageContent = (content: string | Array<{ type: string; text: string }>): string => {
    if (typeof content === 'string') return content;
    return content.map(c => c.text || '').join('');
  };

  const getThreadName = (thread: Thread) => {
    const date = new Date(thread.created_at);
    return `Chat - ${date.toLocaleString()}`;
  };

  return (
    // Root remains full height. Ensure children can shrink by adding min-h-0 on flex columns below.
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar with threads */}
      <div
        className={cn(
          // make sidebar a column that can shrink so its scrollable child can work
          "bg-white border-r flex flex-col transition-all duration-300 min-h-0",
          isSidebarCollapsed ? "w-16" : "w-80"
        )}
      >
        {!isSidebarCollapsed && (
          <>
            <div className="p-4 border-b flex-shrink-0">
              <Button variant="ghost" onClick={onBack} className="mb-3 w-full justify-start">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Dashboard
              </Button>
              <div className="flex items-center gap-2 mb-2">
                <Bot className="w-5 h-5 text-purple-600" />
                <h2 className="truncate">{assistant.name}</h2>
              </div>
              <p className="text-sm text-gray-600 line-clamp-2">{assistant.description}</p>
            </div>

            <div className="p-4 border-b flex-shrink-0 space-y-2">
              <Button onClick={handleCreateNewThread} className="w-full">
                <Plus className="w-4 h-4 mr-2" />
                New Chat
              </Button>
            </div>
          </>
        )}

        {/* Sidebar scrollable area: allow native scroll and ensure proper shrinking with min-h-0 */}
        <ScrollArea className="flex-1 overflow-auto min-h-0">
          {!isSidebarCollapsed && (
            <div className="p-2">
              {threads.map((thread) => (
                <button
                  key={thread.thread_id}
                  onClick={() => setSelectedThread(thread)}
                  className={cn(
                    'w-full p-3 rounded-lg text-left hover:bg-gray-100 transition-colors mb-1',
                    selectedThread?.thread_id === thread.thread_id && 'bg-purple-50 hover:bg-purple-100'
                  )}
                >
                  <div className="flex items-center gap-2">
                    <MessageSquare className="w-4 h-4 text-gray-400" />
                    <span className="text-sm truncate">{getThreadName(thread)}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </ScrollArea>

        <div className="p-2 border-t flex-shrink-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
            className="w-full"
          >
            {isSidebarCollapsed ? (
              <ChevronRight className="w-4 h-4" />
            ) : (
              <ChevronLeft className="w-4 h-4" />
            )}
          </Button>
        </div>
      </div>

      {/* Chat area */}
      {/* Chat column: make it a flex column that can shrink so the inner ScrollArea scrolls */}
      <div className="flex-1 flex flex-col min-h-0">
        {!selectedThread ? (
          <div className="flex-1 flex items-center justify-center min-h-0">
            <div className="text-center">
              <MessageSquare className="w-16 h-16 mx-auto mb-4 text-gray-300" />
              <h3 className="mb-2">No chat selected</h3>
              <p className="text-sm text-gray-600 mb-4">
                Select a chat or create a new one to start
              </p>
              <Button onClick={handleCreateNewThread}>
                <Plus className="w-4 h-4 mr-2" />
                Create New Chat
              </Button>
            </div>
          </div>
        ) : (
          <>
            {/* Chat history scrollable area: native scroll and proper shrinking */}
            <ScrollArea className="flex-1 p-6 overflow-auto min-h-0">
              <div className="max-w-4xl mx-auto space-y-6">
                {isLoading && messages.length === 0 ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
                  </div>
                ) : messages.length === 0 && !isSending ? (
                  <div className="text-center py-12">
                    <p className="text-gray-500">No messages yet. Start the conversation!</p>
                  </div>
                ) : (
                  messages.map((message, index) => (
                    <div
                      key={message.id || index}
                      className={cn(
                        'flex gap-3',
                        message.type === 'human' ? 'justify-end' : 'justify-start'
                      )}
                    >
                      {message.type !== 'human' && (
                        <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center flex-shrink-0">
                          <Bot className="w-4 h-4 text-purple-600" />
                        </div>
                      )}

                      <Card
                        className={cn(
                          'p-4 max-w-[80%]',
                          message.type === 'human'
                            ? 'bg-purple-600 text-white'
                            : 'bg-white'
                        )}
                      >
                        {message.type === 'human' ? (
                          <div className="whitespace-pre-wrap break-words text-sm">
                            {formatMessageContent(message.content)}
                          </div>
                        ) : (
                          <div className="prose prose-sm max-w-none prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-0">
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              components={{
                                code({ node, inline, className, children, ...props }) {
                                  const match = /language-(\w+)/.exec(className || '');
                                  return !inline && match ? (
                                    <SyntaxHighlighter
                                      style={vscDarkPlus}
                                      language={match[1]}
                                      PreTag="div"
                                      className="rounded-md my-2"
                                      {...props}
                                    >
                                      {String(children).replace(/\n$/, '')}
                                    </SyntaxHighlighter>
                                  ) : (
                                    <code className="bg-gray-100 px-1 py-0.5 rounded text-sm" {...props}>
                                      {children}
                                    </code>
                                  );
                                },
                                a({ node, children, ...props }) {
                                  return (
                                    <a
                                      className="text-purple-600 hover:underline"
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      {...props}
                                    >
                                      {children}
                                    </a>
                                  );
                                },
                              }}
                            >
                              {formatMessageContent(message.content)}
                            </ReactMarkdown>
                          </div>
                        )}
                      </Card>

                      {message.type === 'human' && (
                        <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0">
                          <User className="w-4 h-4 text-gray-600" />
                        </div>
                      )}
                    </div>
                  ))
                )}
                {toolCall && (
                  <div className="flex gap-3 justify-start">
                    <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center flex-shrink-0">
                      <Bot className="w-4 h-4 text-purple-600" />
                    </div>
                    <Card className="p-4 max-w-[80%] bg-white">
                      <div className="flex items-center gap-2 text-sm text-gray-600">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span> Calling tool: <strong>{toolCall.name} </strong></span>
                      </div>
                    </Card>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>

            <div className="border-t bg-white p-4 flex-shrink-0">
              <div className="max-w-4xl mx-auto flex gap-3">
                <Textarea
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  placeholder="Type your message..."
                  disabled={isSending}
                  rows={1}
                  className="resize-none"
                />
                <Button
                  onClick={handleSendMessage}
                  disabled={!inputMessage.trim() || isSending}
                  className="px-6"
                >
                  {isSending && !toolCall ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}