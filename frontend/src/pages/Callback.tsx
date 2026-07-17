import { useHandleSignInCallback } from '@logto/react';
import { useNavigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';

export default function Callback() {
  const navigate = useNavigate();
  const { isLoading } = useHandleSignInCallback(() => {
    // Navigate to root when sign in is successful
    navigate('/');
  });

  if (isLoading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-[hsl(var(--bg-primary))]">
        <div className="flex flex-col items-center gap-4 text-[hsl(var(--brand-primary))]">
          <Loader2 size={48} className="animate-spin" />
          <p className="text-lg font-medium">Logger ind...</p>
        </div>
      </div>
    );
  }

  return null;
}
