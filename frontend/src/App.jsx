import { useState } from 'react';
import Chart from './Chart';
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";

export default function App() {
  const [asset, setAsset] = useState('BTCUSDT');
  const [interval, setInterval] = useState('1m');

  const isLive = asset === 'BTCUSDT' && interval === '1m';
  const isReplay = asset === 'AAPL' && interval === '1m';

  return (
    <div className="flex flex-col h-screen w-full bg-[#0a0a0a] text-[#e5e2e1] font-body-md overflow-hidden dark">
      {/* Header */}
      <header className="bg-[#141313] border-b border-[#1f1f1f] flex justify-between items-center h-12 px-4 w-full shrink-0">
        <div className="font-headline-md text-[20px] font-bold tracking-tighter text-[#e5e2e1]">
          UNIFIED MARKET PIPELINE
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-[#8e9192] uppercase font-semibold">
            {isLive ? 'LIVE STREAM CONNECTED' : isReplay ? 'MARKET REPLAY ACTIVE' : 'HISTORICAL MODE'}
          </span>
          {isLive && <div className="w-[6px] h-[6px] rounded-full bg-[#00ff88] animate-pulse"></div>}
          <span className="material-symbols-outlined text-[#8e9192] ml-2">sensors</span>
        </div>
      </header>

      {/* Control Panel */}
      <div className="bg-[#111111] border-b border-[#1f1f1f] flex items-center h-14 px-4 gap-6 shrink-0">
        <Select value={asset} onValueChange={setAsset}>
          <SelectTrigger className="w-[140px] bg-[#1f1f1f] border-none h-8 text-[11px] font-semibold tracking-wide uppercase">
            <SelectValue placeholder="Select Asset" />
          </SelectTrigger>
          <SelectContent className="bg-[#111111] border-[#1f1f1f] text-white">
            <SelectItem value="BTCUSDT">BTCUSDT</SelectItem>
            <SelectItem value="AAPL">AAPL</SelectItem>
          </SelectContent>
        </Select>

        <div className="flex items-center gap-2 border border-[#1f1f1f] rounded px-2 py-1 bg-[#0e0e0e]">
          <div className={`w-1.5 h-1.5 rounded-full ${isLive ? 'bg-[#00ff88]' : isReplay ? 'bg-[#ffb4ab]' : 'bg-[#8e9192]'}`}></div>
          <span className={`text-[11px] font-semibold ${isLive ? 'text-[#00ff88]' : isReplay ? 'text-[#ffb4ab]' : 'text-[#8e9192]'}`}>
            {isLive ? 'LIVE' : isReplay ? 'REPLAY' : 'STATIC'}
          </span>
        </div>

        <div className="h-4 w-px bg-[#1f1f1f]"></div>

        <div className="flex items-center gap-1">
          {['1m', '30m', '1d', '7d'].map((tf) => (
            <Button
              key={tf} variant="ghost" size="sm" onClick={() => setInterval(tf)}
              className={`h-7 px-3 text-[11px] font-semibold rounded ${
                interval === tf ? 'bg-[#1f1f1f] text-white hover:bg-[#1f1f1f]' : 'text-[#8e9192] hover:text-white hover:bg-[#2b2a2a]'
              }`}
            >
              {tf}
            </Button>
          ))}
        </div>
      </div>

      {/* Main Workspace */}
      <div className="flex flex-1 overflow-hidden p-4 gap-4">
        <Card className="flex-1 bg-[#111111] border-[#1f1f1f] rounded-lg overflow-hidden flex flex-col relative rounded-none shadow-none">
          <CardContent className="p-0 flex-1 flex h-full">
            <Chart asset={asset} interval={interval} />
          </CardContent>
        </Card>

        <Card className="w-1/4 min-w-[280px] bg-[#111111] border-[#1f1f1f] rounded-none shadow-none flex flex-col">
          <div className="h-10 border-b border-[#1f1f1f] flex items-center px-4">
            <span className="text-[11px] font-semibold text-[#8e9192] uppercase tracking-widest">ORDER FLOW</span>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            <div className="flex justify-between px-2 py-1 text-[#8e9192] text-[11px] opacity-50">
              <span>PRICE</span><span>SIZE</span><span>TIME</span>
            </div>
            <div className="flex justify-between px-2 py-1 font-data-md text-[13px]">
              <span className="text-[#00ff88]">65,050.23</span>
              <span className="text-[#e5e2e1]">0.420</span>
              <span className="text-[#8e9192]">14:02:31</span>
            </div>
            <div className="flex justify-between px-2 py-1 font-data-md text-[13px] bg-[#0e0e0e]">
              <span className="text-[#ff3333]">65,050.00</span>
              <span className="text-[#e5e2e1]">1.250</span>
              <span className="text-[#8e9192]">14:02:30</span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}