import React from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { ChevronLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function ReleaseNotesPage() {
  const { t } = useTranslation();
  
  const versionsObj = t('releaseNotes.versions', { returnObjects: true }) as Record<string, { version: string, date: string, changes: string[] }>;
  
  const versions = Object.values(versionsObj || {}).reverse();

  return (
    <div className="p-4 md:p-8 max-w-4xl mx-auto space-y-6 pb-28 md:pb-8">
      <div className="mb-6 flex items-center gap-4">
        <Link 
          to="/settings" 
          className="p-2 rounded-full hover:bg-[hsl(var(--bg-tertiary))] transition-colors text-[hsl(var(--text-secondary))]"
        >
          <ChevronLeft size={24} />
        </Link>
        <div>
          <motion.h1 
            initial={{ y: -10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="text-3xl font-bold text-[hsl(var(--text-primary))]"
          >
            {t('releaseNotes.title')}
          </motion.h1>
          <motion.p 
            initial={{ y: -5, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="text-muted mt-2"
          >
            {t('releaseNotes.description')}
          </motion.p>
        </div>
      </div>

      <div className="space-y-8">
        {versions.map((v, i) => (
          <motion.div 
            key={v.version}
            initial={{ opacity: 0, y: 10 }} 
            animate={{ opacity: 1, y: 0 }} 
            transition={{ delay: 0.15 + i * 0.1 }}
            className="relative pl-8 border-l-2 border-[hsl(var(--border-color))]"
          >
            <div className="absolute w-4 h-4 bg-[hsl(var(--brand-primary))] rounded-full -left-[9px] top-1 border-4 border-[hsl(var(--bg-primary))]" />
            
            <div className="mb-2 flex items-baseline gap-3">
              <h2 className="text-xl font-bold text-[hsl(var(--text-primary))]">{v.version}</h2>
              <span className="text-sm text-[hsl(var(--text-secondary))]">{v.date}</span>
            </div>
            
            <ul className="list-disc pl-5 space-y-2 text-[hsl(var(--text-secondary))]">
              {Array.isArray(v.changes) && v.changes.map((change, idx) => (
                <li key={idx} className="pl-1 leading-relaxed">
                  {change}
                </li>
              ))}
            </ul>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
