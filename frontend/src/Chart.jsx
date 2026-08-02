import { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';

export default function Chart({ asset, interval, onTrade }) {
  const chartContainerRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const seriesRef = useRef(null);
  const wsRef = useRef(null);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // 1. Initialize Chart
    const chart = createChart(chartContainerRef.current, {
      layout: { background: { type: 'solid', color: '#0e0e0e' }, textColor: '#8e9192' },
      grid: { vertLines: { color: '#1f1f1f' }, horzLines: { color: '#1f1f1f' } },
      crosshair: { mode: 0 },
      timeScale: { timeVisible: true, secondsVisible: false },
    });

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#00ff88', downColor: '#ff3333', borderVisible: false,
      wickUpColor: '#00ff88', wickDownColor: '#ff3333',
    });

    chartInstanceRef.current = chart;
    seriesRef.current = candlestickSeries;

    const handleResize = () => chart.applyOptions({ width: chartContainerRef.current.clientWidth });
    window.addEventListener('resize', handleResize);

    // 2. Fetch and Process Data via Proxy
    const loadData = async () => {
      try {
        // Use VITE_API_URL if in production, fallback to proxy if local
        const API_URL = import.meta.env.VITE_API_URL || '';
        const response = await fetch(`${API_URL}/api/v1/candles?asset=${asset}&interval=${interval}`);
        const data = await response.json();

        const parsedData = data.map(d => ({
          time: Math.floor(new Date(d.time).getTime() / 1000),
          open: d.open, high: d.high, low: d.low, close: d.close,
        })).sort((a, b) => a.time - b.time);

        // SCENARIO A: Market Replay
        if (asset === 'AAPL' && interval === '1m') {
          candlestickSeries.setData([]);
          let idx = 0;
          timerRef.current = setInterval(() => {
            if (idx < parsedData.length) {
              candlestickSeries.update(parsedData[idx]);
              idx++;
            } else clearInterval(timerRef.current);
          }, 50);
        } 
        // SCENARIO B: Live Websocket
        else if (asset === 'BTCUSDT' && interval === '1m') {
          candlestickSeries.setData(parsedData);
          let lastCandle = parsedData.length > 0 ? { ...parsedData[parsedData.length - 1] } : null;

          // Use VITE_WS_URL if in production, fallback to local proxy
          const WS_URL = import.meta.env.VITE_WS_URL || `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;
          wsRef.current = new WebSocket(`${WS_URL}/ws/BTC`);
          
          wsRef.current.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            const price = msg.price;
            const quantity = msg.quantity;
            const msgTimeSec = Math.floor(msg.time / 1000);
            const minuteTime = msgTimeSec - (msgTimeSec % 60);

            if (onTrade) {
                onTrade({
                    price: price,
                    size: quantity,
                    time: new Date(msg.time).toLocaleTimeString(),
                    isBuy: !msg.is_buyer_maker // If buyer is NOT maker, it's a market buy (taker)
                });
            }

            if (!lastCandle) {
              lastCandle = { time: minuteTime, open: price, high: price, low: price, close: price };
            } else if (minuteTime === lastCandle.time) {
              lastCandle.close = price;
              lastCandle.high = Math.max(lastCandle.high, price);
              lastCandle.low = Math.min(lastCandle.low, price);
            } else if (minuteTime > lastCandle.time) {
              lastCandle = { time: minuteTime, open: price, high: price, low: price, close: price };
            }
            candlestickSeries.update(lastCandle);
          };
        } 
        // SCENARIO C: Static Historical
        else {
          candlestickSeries.setData(parsedData);
        }
      } catch (error) {
        console.error("Failed to fetch data:", error);
      }
    };

    loadData();

    // 3. Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      if (timerRef.current) clearInterval(timerRef.current);
      if (wsRef.current) wsRef.current.close();
      chart.remove();
    };
  }, [asset, interval]);

  return <div ref={chartContainerRef} className="w-full h-full min-h-[500px] flex-1 bg-[#0e0e0e]" />;
}