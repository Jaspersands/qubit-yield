import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line,
  LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import type { AnalysisResponse } from './types';
import { money, optionColors, optionNames, percent } from './utils';
import { useState } from 'react';

const tooltipStyle = { backgroundColor: '#fffef8', border: '1px solid #d8dcd2', borderRadius: 12, boxShadow: '0 8px 25px #10242112', fontSize: 12, padding: '12px 14px' };
const tick = { fill: '#7a837d', fontSize: 11, fontFamily: 'inherit' };

export function ValueChart({ data }: { data: AnalysisResponse }) {
  const values = data.options.filter((option) => option.id !== 'baseline').map((option) => ({
    name: option.id === 'calibration' ? 'Calibration' : option.id === 'pulse' ? 'Pulse gates' : 'Controls',
    value: option.customer_npv_usd, id: option.id,
  }));
  return <div className="chart-container value-chart" role="img" aria-label="Customer net present value by proposal after the proposed contract fee">
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={values} layout="vertical" margin={{ top: 10, right: 20, bottom: 0, left: 0 }} barSize={27}>
        <CartesianGrid stroke="#e6e8df" horizontal={false} strokeDasharray="3 4" />
        <XAxis type="number" tickFormatter={(value: number) => money(value)} tick={tick} axisLine={false} tickLine={false} domain={['auto', 'auto']} />
        <YAxis type="category" dataKey="name" tick={{ ...tick, fill: '#45544b', fontSize: 12 }} axisLine={false} tickLine={false} width={83} />
        <Tooltip cursor={{ fill: '#e9ebe4' }} contentStyle={tooltipStyle} formatter={(value) => [money(Number(value), false), 'Customer NPV']} />
        <ReferenceLine x={0} stroke="#a9b3a7" strokeWidth={1.3} />
        <Bar dataKey="value" radius={[5, 5, 5, 5]} animationDuration={650}>
          {values.map((value) => <Cell key={value.id} fill={optionColors[value.id]} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  </div>;
}

export function DepthChart({ data }: { data: AnalysisResponse }) {
  if (!data.depth_curve?.length) return <div className="chart-empty">Run the experiment suite to generate the depth sweep.</div>;
  return <div className="chart-container depth-chart" role="img" aria-label="Mirror circuit success probability as circuit depth increases">
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data.depth_curve} margin={{ top: 12, right: 18, bottom: 5, left: 0 }}>
        <defs><linearGradient id="pulseArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#a8c96f" stopOpacity={0.3} /><stop offset="100%" stopColor="#a8c96f" stopOpacity={0} /></linearGradient></defs>
        <CartesianGrid stroke="#e3e7dd" vertical={false} strokeDasharray="3 4" />
        <XAxis dataKey="layers" tick={tick} tickLine={false} axisLine={false} label={{ value: 'Two-qubit layers', position: 'insideBottom', offset: -3, fill: '#7a837d', fontSize: 10 }} height={36} />
        <YAxis tickFormatter={(value: number) => percent(value, 0)} tick={tick} axisLine={false} tickLine={false} domain={[0, 1]} width={38} />
        <Tooltip contentStyle={tooltipStyle} formatter={(value, name) => [percent(Number(value)), name === 'pulse' ? 'Optimized gates' : 'Current gates']} labelFormatter={(value) => `${value} layers`} />
        <Area type="monotone" dataKey="pulse" name="pulse" stroke="#769d42" fill="url(#pulseArea)" strokeWidth={2.7} dot={{ r: 3, strokeWidth: 2, fill: '#fffef8' }} activeDot={{ r: 5 }} />
        <Line type="monotone" dataKey="baseline" name="baseline" stroke="#899a93" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 3, strokeWidth: 2, fill: '#fffef8' }} />
      </AreaChart>
    </ResponsiveContainer>
  </div>;
}

export function CashflowChart({ data }: { data: AnalysisResponse }) {
  if (!data.cashflows?.length) return null;
  return <div className="chart-container cashflow-chart" role="img" aria-label="Annual incremental net cashflows including the contract fee">
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data.cashflows} margin={{ top: 10, right: 18, bottom: 0, left: 8 }}>
        <CartesianGrid stroke="#e3e7dd" vertical={false} strokeDasharray="3 4" />
        <XAxis dataKey="year" tickFormatter={(value: number) => value === 0 ? 'Upfront' : `Year ${value}`} tick={tick} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={(value: number) => money(value)} tick={tick} axisLine={false} tickLine={false} width={52} />
        <ReferenceLine y={0} stroke="#a9b3a7" />
        <Tooltip contentStyle={tooltipStyle} formatter={(value, name) => [money(Number(value), false), optionNames[String(name)] || name]} labelFormatter={(value) => Number(value) === 0 ? 'Upfront costs' : `Year ${value}`} />
        <Legend formatter={(value: string) => optionNames[value]} wrapperStyle={{ fontSize: 11, paddingTop: 18 }} iconType="circle" iconSize={7} />
        <Line dataKey="calibration" type="monotone" stroke={optionColors.calibration} strokeWidth={2} dot={{ r: 3 }} />
        <Line dataKey="pulse" type="monotone" stroke="#6f963d" strokeWidth={2.7} dot={{ r: 3 }} />
        <Line dataKey="control" type="monotone" stroke={optionColors.control} strokeWidth={2} dot={{ r: 3 }} />
      </LineChart>
    </ResponsiveContainer>
  </div>;
}

export function Schedule({ data }: { data: AnalysisResponse }) {
  return <div className="schedule-chart">
    {(['baseline', 'calibration'] as const).map((key) => {
      const day = data.schedule[key];
      return <div className="schedule-row" key={key}>
        <div className="schedule-label"><span>{key === 'baseline' ? 'Today' : 'With AI'}</span><span>{day.booked.toFixed(1)}h booked</span></div>
        <div className="schedule-track" aria-label={`${key}: ${day.calibration.toFixed(2)} hours calibration, ${day.booked.toFixed(2)} hours booked, ${day.idle.toFixed(2)} hours idle`}>
          <div className="schedule-calibration" style={{ width: `${day.calibration / 24 * 100}%` }} title={`${day.calibration.toFixed(2)} hours calibration`}>{day.calibration >= 3 && `${day.calibration.toFixed(1)}h`}</div>
          <div className="schedule-booked" style={{ width: `${day.booked / 24 * 100}%` }} title={`${day.booked.toFixed(2)} hours booked`}>{day.booked >= 3 && `${day.booked.toFixed(1)}h`}</div>
          <div className="schedule-idle" style={{ width: `${day.idle / 24 * 100}%` }} title={`${day.idle.toFixed(2)} hours idle`}>{day.idle >= 3 && `${day.idle.toFixed(1)}h`}</div>
        </div>
      </div>;
    })}
    <div className="legend-row"><span><i className="dot blue" />Calibration</span><span><i className="dot green" />Booked</span><span><i className="dot grey" />Idle / unavailable demand</span></div>
  </div>;
}

export function Heatmap({ data }: { data: AnalysisResponse }) {
  const [hover, setHover] = useState<{ value_per_hour: number; realization: number } | null>(null);
  const cells = data.heatmap || [];
  if (!cells.length) return <div className="chart-empty">Sensitivity results will appear after analysis.</div>;
  const values = [...new Set(cells.map((cell) => cell.value_per_hour))].sort((a, b) => a - b);
  const rows = [...new Set(cells.map((cell) => cell.realization))].sort((a, b) => b - a);
  const active = cells.find((cell) => cell.value_per_hour === hover?.value_per_hour && cell.realization === hover?.realization) || cells.find((cell) => cell.winner === 'pulse') || cells[0];
  return <div className="heatmap-wrap">
    <div className="heatmap-axis-label">Value realization</div>
    <div className="heatmap-grid" style={{ gridTemplateColumns: `36px repeat(${values.length}, minmax(8px, 1fr))` }}>
      {rows.map((row) => <div className="heatmap-display-row" key={row}>
        <div className="heatmap-row-label">{percent(row, 0)}</div>
        {values.map((value) => {
          const cell = cells.find((item) => item.realization === row && item.value_per_hour === value);
          const color = cell && cell.npv > 0 ? optionColors[cell.winner] || '#b3d46d' : '#e7e9e0';
          return <button type="button" className={`heatmap-cell ${hover?.value_per_hour === value && hover?.realization === row ? 'selected' : ''}`} style={{ background: color }} key={value}
            aria-label={`${money(value, false)} per productive hour, ${percent(row, 0)} realization: ${cell ? `${optionNames[cell.winner] || cell.winner}, ${money(cell.npv)} NPV` : 'No result'}`}
            onFocus={() => cell && setHover(cell)} onMouseEnter={() => cell && setHover(cell)} onClick={() => cell && setHover(cell)} />;
        })}
      </div>)}
      <span />{values.map((value) => <span className="heatmap-col-label" key={value}>{money(value)}</span>)}
    </div>
    <div className="heatmap-axis-bottom">Value per productive hour</div>
    <div className="heatmap-readout"><i style={{ background: active.npv > 0 ? optionColors[active.winner] : '#aeb6a7' }} /><span>{active.npv > 0 ? optionNames[active.winner] || active.winner : 'No positive-NPV contract'}</span><strong>{money(active.npv)}</strong></div>
    <div className="chart-footnote">Each cell chooses the highest customer NPV. Grey means none of the proposed contracts pays back.</div>
  </div>;
}

export function Tornado({ data }: { data: AnalysisResponse }) {
  const entries = (data.sensitivities || []).slice(0, 6);
  if (!entries.length) return null;
  const min = Math.min(0, ...entries.flatMap((entry) => [entry.low_npv, entry.high_npv]));
  const max = Math.max(0, ...entries.flatMap((entry) => [entry.low_npv, entry.high_npv]));
  const range = max - min || 1;
  return <div className="tornado">
    {entries.map((entry) => {
      const a = Math.min(entry.low_npv, entry.high_npv), b = Math.max(entry.low_npv, entry.high_npv);
      return <div className="tornado-row" key={entry.parameter}>
        <span className="tornado-name" title={entry.label}>{entry.label}</span>
        <div className="tornado-track" title={`${entry.low} to ${entry.high}: ${money(entry.low_npv)} to ${money(entry.high_npv)}`}>
          <i className="tornado-zero" style={{ left: `${-min / range * 100}%` }} />
          <i className="tornado-bar" style={{ left: `${(a - min) / range * 100}%`, width: `${Math.max(1, (b - a) / range * 100)}%` }} />
        </div><span className="tornado-range">{money(a)} / {money(b)}</span>
      </div>;
    })}
    <div className="chart-footnote">One assumption changes at a time. Bars show the customer NPV range for {(optionNames[entries[0]?.option_id || 'pulse'] || 'the selected proposal').toLowerCase()}.</div>
  </div>;
}
