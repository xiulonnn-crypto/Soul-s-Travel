import { useEffect, useRef } from 'react'
import ReactECharts from 'echarts-for-react'
import * as echarts from 'echarts'
import worldJson from '../../assets/world.json'
import { toEnglishCountry } from '../../utils/countryMap'

let registered = false
function ensureMapRegistered() {
  if (!registered) {
    echarts.registerMap('world', worldJson)
    registered = true
  }
}

export default function WorldFootprintMap({ countries }) {
  const ref = useRef(null)
  useEffect(() => { ensureMapRegistered() }, [])

  const entries = (countries || []).map(([zh, count]) => ({
    name: toEnglishCountry(zh),
    value: count,
    zhName: zh,
  }))
  const values = entries.map(e => e.value)
  const max = values.length ? Math.max(...values) : 1

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: (p) => {
        if (p.data && p.data.zhName) {
          return `<b>${p.data.zhName}</b><br/>去过 ${p.data.value} 次`
        }
        return p.name
      },
    },
    visualMap: {
      min: 0,
      max: Math.max(max, 1),
      left: 12,
      bottom: 12,
      text: ['多', '少'],
      inRange: { color: ['#e6f4ff', '#0099ff', '#003a70'] },
      calculable: false,
      itemWidth: 10,
      itemHeight: 80,
      textStyle: { fontSize: 11, color: '#8e99a4' },
    },
    series: [
      {
        type: 'map',
        map: 'world',
        roam: true,
        zoom: 1.1,
        scaleLimit: { min: 1, max: 6 },
        itemStyle: {
          areaColor: '#f0f2f5',
          borderColor: '#fff',
          borderWidth: 0.4,
        },
        emphasis: {
          itemStyle: { areaColor: '#ff9500' },
          label: { show: false },
        },
        select: { disabled: true },
        data: entries,
      },
    ],
  }

  return (
    <div ref={ref} style={{ width: '100%', height: '100%', minHeight: 320 }}>
      <ReactECharts
        option={option}
        style={{ height: '100%', width: '100%' }}
        notMerge
        lazyUpdate
      />
    </div>
  )
}
