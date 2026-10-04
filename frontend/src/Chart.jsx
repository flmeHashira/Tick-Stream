import { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';

export default function Chart({ asset, interval, onTrade, onReady, onError }) {
  const chartContainerRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const seriesRef = useRef(null);
  const wsRef = useRef(null);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    let cancelled = false;
    let readySignaled = false;
    let historicalLoaded = false;
    let firstLiveTradeReceived = false;
    const pendingLiveTrades = [];

    // 1. Initialize Chart
    const chart = createChart(chartContainerRef.current, {
      layout: { background: { type: 'solid', color: '#0e0e0e' }, textColor: '#8e9192' },
      grid: { vertLines: { color: '#1f1f1f' }, horzLines: { color: '#1f1f1f' } },
      crosshair: { mode: 0 },
      timeScale: { timeVisible: true, secondsVisible: false, handleScroll: true, handleScale: true },
    });

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#00ff88', downColor: '#ff3333', borderVisible: false,
      wickUpColor: '#00ff88', wickDownColor: '#ff3333',
    });

    chartInstanceRef.current = chart;
    seriesRef.current = candlestickSeries;

    const handleResize = () => chart.applyOptions({ width: chartContainerRef.current.clientWidth });
    window.addEventListener('resize', handleResize);

    const signalReady = () => {
      if (cancelled || readySignaled) return;

      if (asset === 'BTCUSDT' && interval === '1m') {
        if (!historicalLoaded || !firstLiveTradeReceived) return;
      }

      readySignaled = true;
      onReady?.();
    };

    const signalError = (message) => {
      if (!cancelled && !readySignaled) {
        onError?.(message);
      }
    };

    const setInitialView = (dataLength) => {
      if (dataLength <= 0) return;

      if (interval === '1m') {
        const barsToShow = 360;
        const from = Math.max(0, dataLength - barsToShow);

        chart.timeScale().setVisibleLogicalRange({
          from,
          to: dataLength - 1,
        });
      } else {
        chart.timeScale().fitContent();
      }
    };

    // 2. Live Websocket
    let lastCandle = null;

    const applyLiveTrade = (msg) => {
      if (cancelled) return;

      const price = msg.price;
      const msgTimeSec = Math.floor(msg.time / 1000);
      const minuteTime = msgTimeSec - (msgTimeSec % 60);

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

    const connectLiveWebSocket = () => {
      // Use VITE_WS_URL if in production, fallback to local proxy
      const WS_URL = import.meta.env.VITE_WS_URL || `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;
      wsRef.current = new WebSocket(`${WS_URL}/ws/BTC`);

      wsRef.current.onmessage = (event) => {
        if (cancelled) return;

        const msg = JSON.parse(event.data);
        const quantity = msg.quantity;

        if (onTrade) {
          onTrade({
            price: msg.price,
            size: quantity,
            time: new Date(msg.time).toLocaleTimeString(),
            isBuy: !msg.is_buyer_maker // If buyer is NOT maker, it's a market buy (taker)
          });
        }

        firstLiveTradeReceived = true;

        if (!historicalLoaded) {
          if (pendingLiveTrades.length < 1000) {
            pendingLiveTrades.push(msg);
          }
          return;
        }

        applyLiveTrade(msg);
        signalReady();
      };

      wsRef.current.onerror = () => {
        signalError("Live market connection failed");
      };

      wsRef.current.onclose = (event) => {
        if (!cancelled && !readySignaled && !event.wasClean) {
          signalError("Live market connection closed");
        }
      };
    };

    // 3. Fetch and Process Data
    const loadData = async () => {
      try {
        // Use VITE_API_URL if in production, fallback to proxy if local
        const API_URL = import.meta.env.VITE_API_URL || '';

        // Wait until backend data is available
        while (!cancelled) {
          const readyResponse = await fetch(`${API_URL}/ready?asset=${asset}`, { cache: 'no-store' });

          if (readyResponse.ok) break;

          await new Promise(resolve => setTimeout(resolve, 1000));
        }

        if (cancelled) return;

        const response = await fetch(`${API_URL}/api/v1/candles?asset=${asset}&interval=${interval}`);
        if (!response.ok) {
          throw new Error(`Historical data request failed (${response.status})`);
        }

        const data = await response.json();

        if (!Array.isArray(data) || data.length === 0) {
          throw new Error("No historical market data available");
        }

        if (cancelled) return;

        const parsedData = data.map(d => ({
          time: Math.floor(new Date(d.time).getTime() / 1000),
          open: d.open, high: d.high, low: d.low, close: d.close,
        })).sort((a, b) => a.time - b.time);

        // SCENARIO A: Market Replay
        if (asset === 'AAPL' && interval === '1m') {
          candlestickSeries.setData([]);
          let idx = 0;

          timerRef.current = setInterval(() => {
            if (cancelled) {
              clearInterval(timerRef.current);
              return;
            }

            if (idx < parsedData.length) {
              candlestickSeries.update(parsedData[idx]);

              if (idx === 0) {
                signalReady();
              }

              idx++;
            } else {
              clearInterval(timerRef.current);
            }
          }, 50);
        }

        // SCENARIO B: Live Websocket
        else if (asset === 'BTCUSDT' && interval === '1m') {
          candlestickSeries.setData(parsedData);
          setInitialView(parsedData.length);

          lastCandle = parsedData.length > 0 ? { ...parsedData[parsedData.length - 1] } : null;
          historicalLoaded = true;

          // Apply trades that arrived while history was loading
          pendingLiveTrades.forEach(applyLiveTrade);
          pendingLiveTrades.length = 0;

          signalReady();
        }

        // SCENARIO C: Static Historical
        else {
          candlestickSeries.setData(parsedData);
          setInitialView(parsedData.length);
          signalReady();
        }
      } catch (error) {
        if (!cancelled) {
          console.error("Failed to initialize chart:", error);
          signalError(error.message || "Failed to load market data");
        }
      }
    };

    // Start both paths immediately for live mode
    if (asset === 'BTCUSDT' && interval === '1m') {
      connectLiveWebSocket();
    }

    loadData();

    // 4. Cleanup
    return () => {
      cancelled = true;
      window.removeEventListener('resize', handleResize);
      if (timerRef.current) clearInterval(timerRef.current);
      if (wsRef.current) wsRef.current.close();
      chart.remove();
    };
  }, [asset, interval, onTrade, onReady, onError]);

  return <div ref={chartContainerRef} className="w-full h-full min-h-[500px] flex-1 bg-[#0e0e0e]" />;
}