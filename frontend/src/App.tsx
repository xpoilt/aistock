import { useState, useEffect, useRef } from 'react'
import { ConfigProvider, Input, Select, Button, Card, List, Typography, Space, Spin, Badge, App, message } from 'antd'
import { RobotOutlined, SendOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import axios from 'axios'
import './App.css'

const { TextArea } = Input
const { Title, Text } = Typography

interface Agent {
  id: number
  name: string
  system_prompt: string
}

interface Message {
  id: string
  agent: string
  agentKey: string
  content: string
  isUser?: boolean
  timestamp: Date
}

const AGENT_COLORS: Record<string, string> = {
  A: '#1890ff',
  B: '#52c41a',
  C: '#faad14',
  D: '#722ed1',
  E: '#eb2f96',
  F: '#13c2c2'
}

const getAgentInitials = (name: string): string => {
  if (!name) return '??'
  return name.slice(0, 2)
}

const API_BASE = 'http://127.0.0.1:8004'

function AppContent() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [selectedAgentA, setSelectedAgentA] = useState<number | null>(3)
  const [selectedAgentB, setSelectedAgentB] = useState<number | null>(1)
  const [selectedAgentC, setSelectedAgentC] = useState<number | null>(2)
  const [selectedAgentD, setSelectedAgentD] = useState<number | null>(4)
  const [selectedAgentE, setSelectedAgentE] = useState<number | null>(5)
  const [selectedAgentF, setSelectedAgentF] = useState<number | null>(5)
  const [stockCode, setStockCode] = useState('')
  const [userPrompt, setUserPrompt] = useState('')
  const [debateRounds, setDebateRounds] = useState(3)
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [currentStreaming, setCurrentStreaming] = useState<string>('')
  const [currentAgent, setCurrentAgent] = useState<string>('')
  const [currentAgentLabel, setCurrentAgentLabel] = useState<string>('')
  const [stockData, setStockData] = useState<any>(null)
  const [loadingData, setLoadingData] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const decodeUnicode = (str: string): string => {
    if (!str) return '';
    try {
      return str.replace(/\\u([\dabcdef]{4})/gi, (_match, hex) =>
        String.fromCharCode(parseInt(hex, 16))
      );
    } catch {
      return str;
    }
  }

  useEffect(() => {
    fetchAgents()
  }, [])

  useEffect(() => {
    console.log('📊 messages 状态更新:', messages.length, '条')
    if (messages.length > 0) {
      console.log('   已保存的消息列表:')
      messages.forEach((msg, i) => {
        console.log(`   [${i}] ${msg.agent} (${msg.agentKey}): ${msg.content.substring(0, 40)}...`)
      })
    }
  }, [messages])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, currentStreaming])

  const fetchStockData = async () => {
    if (!stockCode.trim()) {
      message.warning('请输入股票代码')
      return
    }
    setLoadingData(true)
    try {
      const res = await axios.post(`${API_BASE}/api/stock/${stockCode}/collect`)
      if (res.data.error) {
        message.error(res.data.error)
        setStockData(null)
      } else {
        setStockData(res.data)
        message.success('股票数据获取成功')
      }
    } catch (err: any) {
      message.error(err.message || '获取股票数据失败')
      setStockData(null)
    } finally {
      setLoadingData(false)
    }
  }

  const fetchAgents = async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/agents`)
      setAgents(res.data)
    } catch (err) {
      message.error('加载 Agent 失败')
    }
  }

  const startDiscussion = async () => {
    if (!userPrompt.trim()) {
      message.warning('请输入讨论主题')
      return
    }
    if (!selectedAgentA || !selectedAgentB || !selectedAgentC || !selectedAgentD || !selectedAgentE || !selectedAgentF) {
      message.warning('请选择所有 6 个 Agent')
      return
    }

    setLoading(true)
    setMessages([])
    setCurrentStreaming('')
    setCurrentAgent('')
    setCurrentAgentLabel('')

    try {
      const response = await fetch(`${API_BASE}/api/discuss`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_prompt: userPrompt,
          stock_code: stockCode || undefined,
          agent_a: selectedAgentA,
          agent_b: selectedAgentB,
          agent_c: selectedAgentC,
          agent_d: selectedAgentD,
          agent_e: selectedAgentE,
          agent_f: selectedAgentF,
          debate_rounds: debateRounds,
          stock_data: stockData || undefined
        })
      })

      if (!response.ok) {
        throw new Error('请求失败')
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let fullContent = ''
      let currentAgentName = ''
      let currentAgentLabel = ''

      console.log('开始处理流式响应...')

      try {
        while (true) {
        const { done, value } = await reader!.read()
        if (done) {
          console.log('流式响应结束')
          break
        }

        buffer += decoder.decode(value, { stream: true })

        const events = buffer.split('\n\n')
        buffer = events.pop() || ''

        for (const event of events) {
          let jsonStr = event.trim()
          if (!jsonStr) continue

          if (jsonStr.startsWith('data: ')) {
            jsonStr = jsonStr.slice(6)
          }

          try {
            const data = JSON.parse(jsonStr)

            if (typeof data.content === 'string') {
              try {
                data.content = JSON.parse(`"${data.content}"`)
              } catch {}
            }
            if (typeof data.agent === 'string') {
              try {
                data.agent = JSON.parse(`"${data.agent}"`)
              } catch {}
            }

            if (data.type === 'thinking_start') {
              currentAgentName = data.agent || ''
              currentAgentLabel = data.agent_label || ''
              fullContent = ''
              setCurrentStreaming('')
              setCurrentAgent(currentAgentName)
              setCurrentAgentLabel(currentAgentLabel)
              console.log('🔔 Agent 开始思考:', data.agent, `(${data.agent_label})`)
            } else if (data.type === 'chunk') {
              fullContent += data.content || ''
              currentAgentName = data.agent || currentAgentName
              currentAgentLabel = data.agent_label || currentAgentLabel
              setCurrentStreaming(fullContent)
              setCurrentAgent(currentAgentName)
              setCurrentAgentLabel(currentAgentLabel)
            } else if (data.type === 'done') {
              if (fullContent && currentAgentName) {
                const newMessage = {
                  id: `${Date.now()}-${Math.random()}`,
                  agent: currentAgentName,
                  agentKey: currentAgentLabel,
                  content: fullContent,
                  timestamp: new Date()
                }
                console.log('💾 准备保存消息:', newMessage.agent, newMessage.agentKey, '内容长度:', fullContent.length)
                setMessages(prev => {
                  const updated = [...prev, newMessage]
                  console.log('✅ 消息已保存到数组，当前消息数:', updated.length)
                  console.log('   已保存的消息列表:')
                  updated.forEach((msg, idx) => {
                    console.log(`   [${idx}] ${msg.agent} (${msg.agentKey})`)
                  })
                  return updated
                })
              }
              fullContent = ''
              setCurrentStreaming('')
            }
          } catch (e) {
            console.log('解析失败:', jsonStr.substring(0, 100))
          }
        }
      }
      } catch (streamErr) {
        console.error('流处理错误:', streamErr)
      }

      setCurrentAgent('')
      setCurrentAgentLabel('')
    } catch (err: any) {
      console.error('讨论失败:', err)
      message.error(err.message || '讨论失败')
    } finally {
      setLoading(false)
    }
  }

  const agentOptions = agents.map(a => ({ label: a.name, value: a.id }))

  return (
    <ConfigProvider theme={{ token: { colorPrimary: '#1677ff' } }}>
      <App>
        <div className="app-container">
          <header className="app-header">
            <Title level={3}><RobotOutlined /> AIStock 多智能体讨论系统</Title>
          </header>

          <div className="app-content">
            <Card className="config-panel" title="讨论配置">
              <Space orientation="vertical" style={{ width: '100%' }} size="middle">
                <div style={{ borderBottom: '1px solid #f0f0f0', paddingBottom: 12 }}>
                  <Text strong>选择 Agent（各角色必须选择）:</Text>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 8 }}>
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>Agent A:</Text>
                      <Select
                        placeholder="选择 Agent A"
                        value={selectedAgentA}
                        onChange={setSelectedAgentA}
                        options={agentOptions}
                        style={{ width: '100%' }}
                        allowClear
                      />
                    </div>
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>Agent B:</Text>
                      <Select
                        placeholder="选择 Agent B"
                        value={selectedAgentB}
                        onChange={setSelectedAgentB}
                        options={agentOptions}
                        style={{ width: '100%' }}
                        allowClear
                      />
                    </div>
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>Agent C:</Text>
                      <Select
                        placeholder="选择 Agent C"
                        value={selectedAgentC}
                        onChange={setSelectedAgentC}
                        options={agentOptions}
                        style={{ width: '100%' }}
                        allowClear
                      />
                    </div>
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>Agent D (综合):</Text>
                      <Select
                        placeholder="选择 Agent D"
                        value={selectedAgentD}
                        onChange={setSelectedAgentD}
                        options={agentOptions}
                        style={{ width: '100%' }}
                        allowClear
                      />
                    </div>
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>Agent E (批判):</Text>
                      <Select
                        placeholder="选择 Agent E"
                        value={selectedAgentE}
                        onChange={setSelectedAgentE}
                        options={agentOptions}
                        style={{ width: '100%' }}
                        allowClear
                      />
                    </div>
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>Agent F (决策):</Text>
                      <Select
                        placeholder="选择 Agent F"
                        value={selectedAgentF}
                        onChange={setSelectedAgentF}
                        options={agentOptions}
                        style={{ width: '100%' }}
                        allowClear
                      />
                    </div>
                  </div>
                </div>

                <div>
                  <Text strong>股票代码:</Text>
                  <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                    <Input
                      placeholder="如 000001"
                      value={stockCode}
                      onChange={e => setStockCode(e.target.value)}
                      style={{ flex: 1 }}
                    />
                    <Button onClick={fetchStockData} loading={loadingData}>
                      获取数据
                    </Button>
                  </div>
                  {stockData && (
                    <div style={{ marginTop: 8, fontSize: 12, color: '#52c41a' }}>
                      ✓ 数据已加载 (最近: {stockData.daily_data?.[0]?.date || 'N/A'})
                    </div>
                  )}
                </div>

                <div>
                  <Text strong>讨论主题:</Text>
                  <TextArea
                    placeholder="输入讨论主题..."
                    value={userPrompt}
                    onChange={e => setUserPrompt(e.target.value)}
                    rows={3}
                    style={{ marginTop: 8 }}
                  />
                </div>

                <div>
                  <Text strong>辩论轮次 (D/E 讨论):</Text>
                  <Input
                    type="number"
                    value={debateRounds}
                    onChange={e => setDebateRounds(parseInt(e.target.value) || 3)}
                    style={{ marginTop: 8, width: 100 }}
                    min={1}
                    max={10}
                  />
                </div>

                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  onClick={startDiscussion}
                  loading={loading}
                  block
                >
                  开始讨论
                </Button>
              </Space>

              <div className="agent-list">
                <Text strong>可用 Agent:</Text>
                <List
                  size="small"
                  dataSource={agents}
                  renderItem={agent => (
                    <List.Item>
                      <Text>{agent.name}</Text>
                    </List.Item>
                  )}
                />
              </div>
            </Card>

            <Card className="chat-panel" title={
              <Space>
                <RobotOutlined />
                <span>讨论区</span>
                {loading && <Badge status="processing" text="讨论进行中..." />}
              </Space>
            }>
              <div className="messages-container">
                {messages.length === 0 && !currentStreaming && (
                  <div className="empty-state">
                    <RobotOutlined style={{ fontSize: 48, color: '#ccc' }} />
                    <Text type="secondary">输入主题开始讨论</Text>
                  </div>
                )}

                {messages.map(msg => (
                  <div key={msg.id} className={`message-item message-${msg.agentKey?.toLowerCase() || 'default'}`}>
                    <div className="message-avatar" style={{ backgroundColor: AGENT_COLORS[msg.agentKey] || '#999' }}>
                      {getAgentInitials(msg.agent)}
                    </div>
                    <div className="message-body">
                      <div className="message-header">
                        <Text strong className="agent-name">{msg.agent}</Text>
                        <Badge count={`Agent ${msg.agentKey}`} style={{ backgroundColor: AGENT_COLORS[msg.agentKey] || '#999' }} />
                        <Text type="secondary" className="message-time">
                          {msg.timestamp.toLocaleTimeString()}
                        </Text>
                      </div>
                      <div className="message-bubble">
                        <div className="message-content">
                          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                            {decodeUnicode(msg.content)}
                          </ReactMarkdown>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}

                {currentStreaming && (
                  <div className="message-item message-streaming">
                    <div className="message-avatar" style={{ backgroundColor: AGENT_COLORS[currentAgentLabel] || '#999', opacity: 0.7 }}>
                      {getAgentInitials(currentAgent)}
                    </div>
                    <div className="message-body">
                      <div className="message-header">
                        <Text strong className="agent-name">{currentAgent}</Text>
                        <Badge count={`Agent ${currentAgentLabel}`} style={{ backgroundColor: AGENT_COLORS[currentAgentLabel] || '#999' }} />
                        <Spin size="small" />
                      </div>
                      <div className="message-bubble streaming">
                        <div className="message-content" style={{whiteSpace: 'pre-wrap'}}>
                          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                            {decodeUnicode(currentStreaming)}
                          </ReactMarkdown>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            </Card>
          </div>
        </div>
      </App>
    </ConfigProvider>
  )
}

export default AppContent