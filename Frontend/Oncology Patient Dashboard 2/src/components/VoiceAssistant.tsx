import { useState, useEffect, useRef } from 'react';
import { Mic, MicOff, Volume2, X, Minimize2, Maximize2, Send, MessageCircle } from 'lucide-react';

interface VoiceAssistantProps {
  onNavigate?: (tab: string) => void;
}

export function VoiceAssistant({ onNavigate }: VoiceAssistantProps) {
  const [isListening, setIsListening] = useState(false);
  const [isExpanded, setIsExpanded] = useState(true); // Auto-expand on load
  const [transcript, setTranscript] = useState('');
  const [response, setResponse] = useState('');
  const [textInput, setTextInput] = useState('');
  const [conversationHistory, setConversationHistory] = useState<Array<{ type: 'user' | 'assistant', text: string }>>([]);
  const recognitionRef = useRef<any>(null);
  const synthRef = useRef<SpeechSynthesis | null>(null);

  useEffect(() => {
    // Initialize Speech Recognition
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = true;
      recognitionRef.current.lang = 'en-US';

      recognitionRef.current.onresult = (event: any) => {
        const current = event.resultIndex;
        const transcriptText = event.results[current][0].transcript;
        setTranscript(transcriptText);

        if (event.results[current].isFinal) {
          processCommand(transcriptText);
        }
      };

      recognitionRef.current.onerror = (event: any) => {
        console.error('Speech recognition error:', event.error);
        setIsListening(false);
      };

      recognitionRef.current.onend = () => {
        setIsListening(false);
      };
    }

    // Initialize Speech Synthesis
    synthRef.current = window.speechSynthesis;

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      if (synthRef.current) {
        synthRef.current.cancel();
      }
    };
  }, []);

  const toggleListening = () => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    } else {
      setTranscript('');
      setResponse('');
      recognitionRef.current?.start();
      setIsListening(true);
    }
  };

  const speak = (text: string) => {
    if (synthRef.current) {
      synthRef.current.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.9;
      utterance.pitch = 1;
      utterance.volume = 1;
      synthRef.current.speak(utterance);
    }
  };

  const processCommand = (command: string) => {
    const lowerCommand = command.toLowerCase();
    let responseText = '';

    // Navigation commands
    if (lowerCommand.includes('show') || lowerCommand.includes('open') || lowerCommand.includes('go to') || lowerCommand.includes('navigate')) {
      if (lowerCommand.includes('diagnosis')) {
        onNavigate?.('diagnosis');
        responseText = 'Opening diagnosis information';
      } else if (lowerCommand.includes('pathology')) {
        onNavigate?.('pathology');
        responseText = 'Opening pathology report';
      } else if (lowerCommand.includes('genomic') || lowerCommand.includes('genetics')) {
        onNavigate?.('genomics');
        responseText = 'Opening genomic test results';
      } else if (lowerCommand.includes('radiology') || lowerCommand.includes('imaging') || lowerCommand.includes('scan')) {
        onNavigate?.('radiology');
        responseText = 'Opening radiology and imaging results';
      } else if (lowerCommand.includes('lab') || lowerCommand.includes('blood')) {
        onNavigate?.('labs');
        responseText = 'Opening laboratory values';
      } else if (lowerCommand.includes('treatment')) {
        onNavigate?.('treatment');
        responseText = 'Opening treatment history';
      } else if (lowerCommand.includes('comorbid')) {
        onNavigate?.('comorbidities');
        responseText = 'Opening comorbidities';
      } else if (lowerCommand.includes('document')) {
        onNavigate?.('documents');
        responseText = 'Opening clinical documents';
      }
    }
    // Patient information queries
    else if (lowerCommand.includes('patient name') || lowerCommand.includes('who is the patient')) {
      responseText = 'The patient is Sarah Mitchell, a 58-year-old female';
    } else if (lowerCommand.includes('age')) {
      responseText = 'The patient is 58 years old';
    } else if (lowerCommand.includes('diagnosis') || lowerCommand.includes('cancer type')) {
      responseText = 'The patient has lung adenocarcinoma, stage 4, diagnosed on May 15, 2024';
    } else if (lowerCommand.includes('egfr') || lowerCommand.includes('mutation')) {
      responseText = 'EGFR status is positive with exon 19 deletion detected';
    } else if (lowerCommand.includes('treatment') || lowerCommand.includes('current therapy')) {
      responseText = 'Current treatment is Osimertinib 80 milligrams daily, started on July 10, 2024';
    } else if (lowerCommand.includes('tnm') || lowerCommand.includes('stage') || lowerCommand.includes('staging')) {
      responseText = 'TNM staging is T2a N2 M1b, which is stage 4A';
    } else if (lowerCommand.includes('response') || lowerCommand.includes('how is the patient doing')) {
      responseText = 'The patient is showing partial response with 28% tumor reduction on current therapy';
    } else if (lowerCommand.includes('next appointment') || lowerCommand.includes('when is the next')) {
      responseText = 'Next appointment is on December 20, 2024 for restaging CT scan';
    } else if (lowerCommand.includes('hemoglobin') || lowerCommand.includes('anemia')) {
      responseText = 'Latest hemoglobin is 10.2 grams per deciliter, which is slightly low';
    } else if (lowerCommand.includes('liver') || lowerCommand.includes('alt') || lowerCommand.includes('ast')) {
      responseText = 'Liver enzymes are mildly elevated. ALT is 58, AST is 52, likely treatment-related';
    } else if (lowerCommand.includes('cea') || lowerCommand.includes('tumor marker')) {
      responseText = 'CEA tumor marker is 4.2 nanograms per milliliter, which is within normal range';
    } else if (lowerCommand.includes('help') || lowerCommand.includes('what can you do')) {
      responseText = 'I can help you navigate the dashboard, retrieve patient information, and answer questions about diagnosis, treatment, lab results, imaging, and genomics. Try saying "show treatment" or "what is the EGFR status?"';
    } else if (lowerCommand.includes('hello') || lowerCommand.includes('hi')) {
      responseText = 'Hello! I\'m your oncology assistant. How can I help you today?';
    } else {
      responseText = 'I\'m not sure I understood that. Try asking about patient information, navigating to a section, or say "help" for more options.';
    }

    setResponse(responseText);
    speak(responseText);
    
    setConversationHistory(prev => [
      ...prev,
      { type: 'user', text: command },
      { type: 'assistant', text: responseText }
    ]);
  };

  const handleTextSubmit = () => {
    if (textInput.trim()) {
      processCommand(textInput);
      setTextInput('');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleTextSubmit();
    }
  };

  if (!isExpanded) {
    return (
      <div className="fixed bottom-6 right-6 z-50">
        <button
          onClick={() => setIsExpanded(true)}
          className="bg-gradient-to-br from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white rounded-full p-5 shadow-2xl transition-all duration-300 hover:scale-110 group relative"
          title="Open Voice Assistant"
        >
          <MessageCircle className="w-7 h-7" />
          <div className="absolute -top-1 -right-1 w-4 h-4 bg-green-500 rounded-full border-2 border-white animate-pulse"></div>
        </button>
      </div>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 bg-white rounded-2xl shadow-2xl border border-gray-200 w-96 z-50 overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-700 text-white px-5 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="bg-white/20 p-2 rounded-lg">
            <MessageCircle className="w-5 h-5" />
          </div>
          <div>
            <span className="font-medium">AI Assistant</span>
            <div className="flex items-center gap-1.5 mt-0.5">
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
              <span className="text-xs text-blue-100">Ready to help</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setIsExpanded(false)}
            className="hover:bg-white/20 p-2 rounded-lg transition-colors"
            title="Minimize"
          >
            <Minimize2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => {
              setIsExpanded(false);
              setConversationHistory([]);
              setTranscript('');
              setResponse('');
            }}
            className="hover:bg-white/20 p-2 rounded-lg transition-colors"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-6 bg-gradient-to-b from-gray-50 to-white">
        {/* Response */}
        {response && (
          <div className="bg-white border border-blue-200 rounded-xl p-4 mb-4 shadow-sm">
            <div className="flex items-start gap-3">
              <div className="bg-blue-100 p-2 rounded-lg flex-shrink-0">
                <Volume2 className="w-4 h-4 text-blue-600" />
              </div>
              <p className="text-sm text-gray-800 leading-relaxed pt-0.5">{response}</p>
            </div>
          </div>
        )}

        {/* Transcript */}
        {transcript && (
          <div className="bg-white border border-gray-200 rounded-xl p-4 mb-4 shadow-sm">
            <p className="text-xs text-gray-500 mb-2 uppercase tracking-wide">Listening...</p>
            <p className="text-sm text-gray-900">{transcript}</p>
          </div>
        )}

        {/* Voice Control */}
        <div className="flex flex-col items-center py-6">
          <button
            onClick={toggleListening}
            className={`relative w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 shadow-lg ${
              isListening
                ? 'bg-gradient-to-br from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 scale-110'
                : 'bg-gradient-to-br from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 hover:scale-105'
            }`}
          >
            {isListening ? (
              <>
                <MicOff className="w-9 h-9 text-white" />
                <div className="absolute inset-0 rounded-full bg-red-400 animate-ping opacity-75"></div>
              </>
            ) : (
              <Mic className="w-9 h-9 text-white" />
            )}
          </button>
          <p className="text-sm text-gray-600 mt-4 font-medium">
            {isListening ? 'Tap to stop' : 'Tap to speak'}
          </p>
        </div>

        {/* Divider */}
        <div className="flex items-center gap-3 my-4">
          <div className="flex-1 h-px bg-gray-300"></div>
          <span className="text-xs text-gray-500 uppercase tracking-wider">or type</span>
          <div className="flex-1 h-px bg-gray-300"></div>
        </div>

        {/* Text Input */}
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            placeholder="Ask me anything..."
            className="flex-1 px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm bg-white shadow-sm"
            onKeyPress={handleKeyPress}
          />
          <button
            onClick={handleTextSubmit}
            disabled={!textInput.trim()}
            className="bg-gradient-to-br from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 disabled:from-gray-300 disabled:to-gray-400 disabled:cursor-not-allowed text-white p-3 rounded-xl transition-all duration-200 shadow-sm hover:shadow-md"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Browser Support Warning */}
      {!recognitionRef.current && (
        <div className="px-5 py-3 bg-amber-50 border-t border-amber-200">
          <div className="flex items-start gap-2">
            <div className="text-amber-600 mt-0.5">⚠️</div>
            <p className="text-xs text-amber-800 leading-relaxed">
              Voice recognition is not supported in your browser. Please use Chrome, Edge, or Safari for voice features.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}