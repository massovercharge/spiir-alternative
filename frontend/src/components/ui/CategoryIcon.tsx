import React from 'react';
import { 
  ShoppingCart, 
  Car, 
  Home, 
  HeartPulse, 
  MonitorPlay, 
  Briefcase, 
  Coins, 
  HelpCircle,
  Coffee,
  Train,
  Wrench,
  PiggyBank,
  TrendingUp,
  TrendingDown
} from 'lucide-react';

export function getCategoryIcon(categoryPath: string, size = 18) {
  const path = categoryPath.toLowerCase();

  // Income
  if (path.includes('indkomst') || path.includes('løn') || path.includes('income')) {
    return <TrendingUp size={size} className="text-success" />;
  }

  // Daily / Groceries
  if (path.includes('dagligvarer') || path.includes('supermarked') || path.includes('groceries')) {
    return <ShoppingCart size={size} />;
  }

  // Coffee/Dining
  if (path.includes('restaurant') || path.includes('café') || path.includes('dining')) {
    return <Coffee size={size} />;
  }

  // Transport
  if (path.includes('transport') || path.includes('bil') || path.includes('dsb')) {
    return <Train size={size} />;
  }

  // Housing
  if (path.includes('bolig') || path.includes('husleje')) {
    return <Home size={size} />;
  }

  // Entertainment
  if (path.includes('fritid') || path.includes('underholdning') || path.includes('abonnement')) {
    return <MonitorPlay size={size} />;
  }

  // Default fallback
  if (path.includes('overførsel')) {
    return <TrendingDown size={size} className="text-muted" />;
  }
  
  return <HelpCircle size={size} className="text-muted" />;
}
