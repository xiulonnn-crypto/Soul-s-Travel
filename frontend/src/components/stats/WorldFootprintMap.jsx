import { useEffect, useMemo, useRef } from 'react'
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

// 递归遍历 GeoJSON Polygon / MultiPolygon 的所有 [lng, lat] 顶点
function walkRingCoords(coords, fn) {
  if (!Array.isArray(coords) || coords.length === 0) return
  if (typeof coords[0] === 'number') {
    fn(coords[0], coords[1])
    return
  }
  for (const c of coords) walkRingCoords(c, fn)
}

// 已知限制：跨经度 180° 的国家（俄罗斯、斐济等）会让经度跨度退化为整圈，
// 当前用户数据未触发；如未来支持需切到反子午线 split 或专用 projection。
function computeBoundingCoords(features, visitedNames, padRatio = 0.08, minSpan = 8) {
  let minLng = Infinity, maxLng = -Infinity
  let minLat = Infinity, maxLat = -Infinity
  let hit = 0
  for (const feature of features) {
    const name = feature && feature.properties && feature.properties.name
    if (!name || !visitedNames.has(name)) continue
    walkRingCoords(feature.geometry && feature.geometry.coordinates, (lng, lat) => {
      if (lng < minLng) minLng = lng
      if (lng > maxLng) maxLng = lng
      if (lat < minLat) minLat = lat
      if (lat > maxLat) maxLat = lat
    })
    hit += 1
  }
  if (!hit || !isFinite(minLng)) return null

  let lngSpan = maxLng - minLng
  let latSpan = maxLat - minLat
  if (lngSpan < minSpan) {
    const cx = (minLng + maxLng) / 2
    minLng = cx - minSpan / 2
    maxLng = cx + minSpan / 2
    lngSpan = minSpan
  }
  if (latSpan < minSpan) {
    const cy = (minLat + maxLat) / 2
    minLat = cy - minSpan / 2
    maxLat = cy + minSpan / 2
    latSpan = minSpan
  }
  const padLng = lngSpan * padRatio
  const padLat = latSpan * padRatio
  minLng = Math.max(-180, minLng - padLng)
  maxLng = Math.min(180, maxLng + padLng)
  minLat = Math.max(-85, minLat - padLat)
  maxLat = Math.min(85, maxLat + padLat)

  return [
    [minLng, maxLat],
    [maxLng, minLat],
  ]
}

export default function WorldFootprintMap({ countries }) {
  const ref = useRef(null)
  useEffect(() => { ensureMapRegistered() }, [])

  const entries = useMemo(() => (
    (countries || []).map(([zh, count]) => ({
      name: toEnglishCountry(zh),
      value: count,
      zhName: zh,
    }))
  ), [countries])

  const boundingCoords = useMemo(() => {
    if (!entries.length) return null
    const visited = new Set(entries.map(e => e.name))
    return computeBoundingCoords(worldJson.features, visited)
  }, [entries])

  const values = entries.map(e => e.value)
  const max = values.length ? Math.max(...values) : 1

  const seriesBase = {
    type: 'map',
    map: 'world',
    roam: true,
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
  }
  const series = boundingCoords
    ? { ...seriesBase, boundingCoords }
    : { ...seriesBase, zoom: 1.1 }

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
    series: [series],
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
