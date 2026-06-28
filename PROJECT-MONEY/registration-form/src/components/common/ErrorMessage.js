import React from 'react';
import Icon from './Icons';

export default function ErrorMessage({ message }) {
  return (
    <div className="mb-4 flex gap-3 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
      <Icon name="alert" className="h-5 w-5 shrink-0 text-red-300" />
      <span>{message}</span>
    </div>
  );
}
