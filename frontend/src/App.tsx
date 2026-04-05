import { useState, useEffect, useRef } from 'react'
import { ConfigProvider, App as AntApp, Input, Select, Button, Card, List, Typography, Space, message, Spin } from 'antd'
import { RobotOutlined, SendOutlined, ClearOutlined } from '@ant-design/icons'
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
  content: string
  isUser?: boolean
  timestamp: Date
}

const API_BASE = 'http://127.0.0.1:8000'

function App() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [selectedAgents, setSelectedAgents] = useState<number[]>([1, 2, 3, 4])
  const [stockCode, setStockCode] = useState('')
  const [userPrompt, setUserPrompt] = useState('')
  const [maxRounds, setMaxRounds] = useState(4)
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [currentStreaming, setCurrentStreaming] = useState<string>('')
  const [stockData, setStockData] = useState<any>(null)
  const [loadingData, setLoadingData] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetchAgents()
  }, [])

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
    if (selectedAgents.length < 2) {
      message.warning('请至少选择 2 个 Agent')
      return
    }

    setLoading(true)
    setMessages([])
    setCurrentStreaming('')

    try {
      const response = await fetch(`${API_BASE}/api/discuss`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_prompt: userPrompt,
          stock_code: stockCode || undefined,
          agent_ids: selectedAgents,
          max_rounds: maxRounds,
          stock_data: stockData || undefined
        })
      })

      if (!response.ok) {
        throw new Error('请求失败')
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let fullContent = ''
      let currentAgent = ''

      while (true) {
        const { done, value } = await reader!.read()
        if (done) break

        const chunk = decoder.decode(value)
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.type === 'chunk') {
                fullContent += data.content
                currentAgent = data.agent
                setCurrentStreaming(fullContent)
              } else if (data.type === 'done') {
                setMessages(prev => [...prev, {
                  id: Date.now().toString(),
                  agent: currentAgent || data.agent,
                  content: fullContent,
                  timestamp: new Date()
                }])
                fullContent = ''
                setCurrentStreaming('')
              }
            } catch (e) {
              // ignore parse errors
            }
          }
        }
      }
    } catch (err: any) {
      message.error(err.message || '讨论失败')
    } finally {
      setLoading(false)
    }
  }

  const agentOptions = agents.map(a => ({ label: a.name, value: a.id }))

  return (
    <ConfigProvider theme={{ token: { colorPrimary: '#1677ff' } }}>
      <AntApp>
        <div className="app-container">
          <header className="app-header">
            <Title level={3}><RobotOutlined /> AIStock 多智能体讨论系统</Title>
          </header>

          <div className="app-content">
            <Card className="config-panel" title="讨论配置">
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                <div>
                  <Text strong>选择 Agent（至少2个）:</Text>
                  <Select
                    mode="multiple"
                    placeholder="选择参与讨论的 Agent"
                    value={selectedAgents}
                    onChange={setSelectedAgents}
                    options={agentOptions}
                    style={{ width: '100%', marginTop: 8 }}
                  />
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
                  <Text strong>讨论轮次:</Text>
                  <Input
                    type="number"
                    value={maxRounds}
                    onChange={e => setMaxRounds(parseInt(e.target.value) || 4)}
                    style={{ marginTop: 8, width: 100 }}
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

            <Card className="chat-panel" title="讨论区">
              <div className="messages-container">
                {messages.length === 0 && !currentStreaming && (
                  <div className="empty-state">
                    <RobotOutlined style={{ fontSize: 48, color: '#ccc' }} />
                    <Text type="secondary">输入主题开始讨论</Text>
                  </div>
                )}

                {messages.map(msg => (
                  <div key={msg.id} className="message-item">
                    <div className="message-header">
                      <Text strong>{msg.agent}</Text>
                    </div>
                    <div className="message-content">
                      {msg.content}
                    </div>
                  </div>
                ))}

                {currentStreaming && (
                  <div className="message-item streaming">
                    <div className="message-header">
                      <Text strong>正在生成...</Text>
                      <Spin size="small" />
                    </div>
                    <div className="message-content">
                      {currentStreaming}
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            </Card>
          </div>
        </div>
      </AntApp>
    </ConfigProvider>
  )
}

export default App
