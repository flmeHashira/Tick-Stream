import { useState } from 'react';
import Chart from './Chart';
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";

export default function App() {
  const [asset, setAsset] = useState('BTCUSDT');
  const [interval, setInterval] = useState('1m');
  const [trades, setTrades] = useState([]);

  const isLive = asset === 'BTCUSDT' && interval === '1m';
  const isReplay = asset === 'AAPL' && interval === '1m';

  const handleTrade = (trade) => {
    setTrades(prev => [trade, ...prev].slice(0, 20));
  };

  const handleAssetChange = (val) => {
    setAsset(val);
    setTrades([]);
  };

  const handleIntervalChange = (val) => {
    setInterval(val);
    setTrades([]);
  };

  return (
    <div className="flex flex-col h-screen w-full bg-[#0a0a0a] text-[#e5e2e1] font-body-md overflow-hidden dark">
      {/* Header */}
      <header className="bg-[#141313] border-b border-[#1f1f1f] flex justify-between items-center h-12 px-4 w-full shrink-0">
        <div className="font-headline-md text-[20px] font-bold tracking-tighter text-[#e5e2e1]">
          Tick Stream
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
        <Select value={asset} onValueChange={handleAssetChange}>
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
              key={tf} 
              variant="ghost" 
              size="sm" 
              onClick={() => handleIntervalChange(tf)}
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
            <Chart asset={asset} interval={interval} onTrade={isLive ? handleTrade : null} />
          </CardContent>
        </Card>

        <Card className="w-1/4 min-w-[280px] bg-[#111111] border-[#1f1f1f] rounded-none shadow-none flex flex-col">
          <div className="h-10 border-b border-[#1f1f1f] flex items-center px-4">
            <span className="text-[11px] font-semibold text-[#8e9192] uppercase tracking-widest">
              {isLive ? 'LIVE ORDER FLOW' : 'MARKET STATS'}
            </span>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {isLive ? (
              <>
                <div className="flex justify-between px-2 py-1 text-[#8e9192] text-[11px] opacity-50 border-b border-[#1f1f1f] mb-2">
                  <span>PRICE</span><span>SIZE</span><span>TIME</span>
                </div>
                {trades.length === 0 && (
                  <div className="text-center text-[#8e9192] text-[11px] mt-4">
                    Waiting for live trades...
                  </div>
                )}
                {trades.map((t, i) => (
                  <div key={i} className="flex justify-between px-2 py-1 font-data-md text-[13px]">
                    <span className={t.isBuy ? 'text-[#00ff88]' : 'text-[#ff3333]'}>
                      {t.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                    <span className="text-[#e5e2e1]">{t.size ? t.size.toFixed(4) : '0.0000'}</span>
                    <span className="text-[#8e9192]">{t.time}</span>
                  </div>
                ))}
              </>
            ) : (
              <div className="p-4 space-y-4">
                <div className="text-[11px] text-[#8e9192] uppercase tracking-widest mb-4 border-b border-[#1f1f1f] pb-2">
                  Historical View
                </div>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-[#8e9192] text-[12px]">Asset</span>
                    <span className="text-[#e5e2e1] text-[12px] font-semibold">{asset}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#8e9192] text-[12px]">Interval</span>
                    <span className="text-[#e5e2e1] text-[12px] font-semibold">{interval}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#8e9192] text-[12px]">Data Source</span>
                    <span className="text-[#e5e2e1] text-[12px] font-semibold">PostgreSQL</span>
                  </div>
                  <div className="mt-4 pt-4 border-t border-[#1f1f1f] text-[11px] text-[#8e9192] leading-relaxed">
                    Live tick data is only available for BTCUSDT 1m. Switch back to view live order flow.
                  </div>
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}