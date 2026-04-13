import React from 'react';
import { useToast } from '../contexts/AppContext';
import { CheckCircle, XCircle, Info, X } from 'lucide-react';

const ToastContainer = () => {
  const { toasts } = useToast();

  const getIcon = (type) => {
    switch (type) {
      case 'success':
        return <CheckCircle className="w-5 h-5 text-[#00E599]" />;
      case 'error':
        return <XCircle className="w-5 h-5 text-red-400" />;
      default:
        return <Info className="w-5 h-5 text-[#00D4FF]" />;
    }
  };

  const getBorderColor = (type) => {
    switch (type) {
      case 'success':
        return 'border-[#00E599]/30';
      case 'error':
        return 'border-red-400/30';
      default:
        return 'border-[#00D4FF]/30';
    }
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          data-testid={`toast-${toast.type}`}
          className={`toast-enter flex items-center gap-3 px-4 py-3 bg-[#111] border ${getBorderColor(
            toast.type
          )} rounded-lg shadow-xl backdrop-blur-xl min-w-[280px] max-w-md`}
        >
          {getIcon(toast.type)}
          <p className="flex-1 text-sm text-white">{toast.message}</p>
        </div>
      ))}
    </div>
  );
};

export default ToastContainer;
