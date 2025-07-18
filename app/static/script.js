// Polyfill for crypto.randomUUID for browsers that don't support it
if (typeof crypto !== 'undefined' && !crypto.randomUUID) {
    crypto.randomUUID = function() {
        // Simple UUID v4 implementation
        return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
            (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
        );
    };
}

document.addEventListener('DOMContentLoaded', function() {
    // Auth elements
    const authContainer = document.getElementById('auth-container');
    const appContainer = document.querySelector('.app-container');
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const showRegister = document.getElementById('show-register');
    const showLogin = document.getElementById('show-login');
    const logoutBtn = document.getElementById('logout-btn');
    const loginError = document.getElementById('login-error');
    const registerError = document.getElementById('register-error');

    // Navigation
    const navItems = document.querySelectorAll('.nav-item');
    const sections = document.querySelectorAll('.content-section');
    const agentsGrid = document.getElementById('agents-grid');
    const agentCountElement = document.getElementById('agent-count');
    const activityList = document.getElementById('activity-list');
    const chatMessages = document.getElementById('chat-messages');
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message-input');
    
    // Modal elements
    const agentEditModal = document.getElementById('agent-edit-modal');
    const sessionDetailModal = document.getElementById('session-detail-modal');
    const closeModalButtons = document.querySelectorAll('.close-modal');
    const editAgentForm = document.getElementById('edit-agent-form');
    const deleteAgentBtn = document.getElementById('delete-agent-btn');
    const sessionsList = document.getElementById('sessions-list');
    const refreshSessionsBtn = document.getElementById('refresh-sessions');
    
    // Dashboard elements
    const sessionCountElement = document.getElementById('session-count');

    // Store conversation state
    let conversationData = {
        conversation_id: '',
        messages: []
    };

    // --- AUTH FUNCTIONS ---
    async function fetchWithAuth(url, options = {}) {
        const token = localStorage.getItem('accessToken');
        const headers = {
            ...options.headers,
            'Authorization': `Bearer ${token}`
        };

        const response = await fetch(url, { ...options, headers });

        if (response.status === 401) {
            logout();
            return Promise.reject('Unauthorized');
        }

        return response;
    }

    function logout() {
        localStorage.removeItem('accessToken');
        showAuth();
    }

    function showAuth() {
        authContainer.style.display = 'flex';
        appContainer.style.display = 'none';
    }

    function showApp() {
        authContainer.style.display = 'none';
        appContainer.style.display = 'grid';
        // Initial data load for the app
        document.querySelector('.nav-item[data-section="dashboard"]').click();
    }

    function checkAuth() {
        const token = localStorage.getItem('accessToken');
        if (token) {
            showApp();
        } else {
            showAuth();
        }
    }

    // --- DATA FETCHING AND RENDERING FUNCTIONS ---
    async function fetchAgents() {
        try {
            const response = await fetchWithAuth('/agents/');
            const agents = await response.json();
            if (agentCountElement) agentCountElement.textContent = agents.length;
            if (agentsGrid) {
                agentsGrid.innerHTML = '';
                if (agents.length === 0) {
                    agentsGrid.innerHTML = '<p class="empty-state">No agents created yet. Use the "Create Agent" tab to create your first agent.</p>';
                } else {
                    agents.forEach(agent => agentsGrid.appendChild(createAgentCard(agent)));
                }
            }
        } catch (error) {
            console.error('Error fetching agents:', error);
        }
    }

    async function fetchSessions() {
        try {
            const response = await fetchWithAuth('/sessions/');
            const sessions = await response.json();
            if (sessionsList) {
                displaySessions(sessions);
                updateSessionFilters(sessions);
            }
            return sessions || [];
        } catch (error) {
            console.error('Error fetching sessions:', error);
            if(sessionsList) sessionsList.innerHTML = '<p class="empty-state">Error loading sessions.</p>';
            return [];
        }
    }

    async function loadApiKeys() {
        try {
            const response = await fetchWithAuth('/settings/api-keys');
            const data = await response.json();
            const keys = data.keys;
            const status = data.status;

            function setKeyField(id, key, isSet) {
                const field = document.getElementById(id);
                if (field) {
                    field.placeholder = isSet ? key : field.placeholder;
                    field.dataset.isSet = isSet ? 'true' : 'false';
                    field.classList.toggle('key-is-set', isSet);
                }
            }

            setKeyField('api-key', keys.OPENAI_API_KEY, status.OPENAI_API_KEY);
            setKeyField('deepseek-api-key', keys.DEEPSEEK_API_KEY, status.DEEPSEEK_API_KEY);
            setKeyField('gemini-api-key', keys.GEMINI_API_KEY, status.GEMINI_API_KEY);
        } catch (error) {
            console.error('Error fetching API keys:', error);
        }
    }

    function createAgentCard(agent) {
        const card = document.createElement('div');
        card.className = 'agent-card';
        card.innerHTML = `
            <div class="agent-header">
                <div class="agent-name">${agent.agentName}</div>
                <div class="agent-model">${agent.llmConfig?.provider ? `${agent.llmConfig.provider} | ${agent.llmConfig.model}` : 'Default LLM'}</div>
            </div>
            <p>${agent.systemPrompt?.substring(0, 100) + (agent.systemPrompt?.length > 100 ? '...' : '') || 'No description'}</p>
            <div class="agent-actions">
                <button class="btn primary">Chat</button>
                <button class="btn secondary"><span class="material-icons">edit</span></button>
            </div>
        `;
                card.querySelector('.btn.primary').onclick = () => {
            localStorage.setItem('currentAgent', JSON.stringify(agent));
            window.location.href = `/chat/${agent.agentId}`;
        };
        card.querySelector('.btn.secondary').onclick = () => openAgentEditModal(agent);
        return card;
    }

    function displaySessions(sessions) {
        sessionsList.innerHTML = '';
        if (sessions.length === 0) {
            sessionsList.innerHTML = '<p class="empty-state">No sessions found.</p>';
            return;
        }
        sessions.forEach(session => {
            const sessionItem = document.createElement('div');
            sessionItem.className = 'session-item';
            const createdDate = new Date(session.created_at).toLocaleString();
            const lastActivityDate = new Date(session.last_activity).toLocaleString();
            sessionItem.innerHTML = `
                <div class="session-info">
                    <div><strong>Session ID:</strong> ${session.session_id.substring(0, 8)}...</div>
                    <div><strong>Agent:</strong> ${session.agent_id}</div>
                    <div><strong>User:</strong> ${session.user_id}</div>
                    <div><strong>Created:</strong> ${createdDate}</div>
                    <div><strong>Last Activity:</strong> ${lastActivityDate}</div>
                </div>
                <div class="session-actions">
                    <button class="btn primary"><span class="material-icons">visibility</span> View</button>
                </div>
            `;
            sessionItem.querySelector('button').onclick = () => viewSessionDetails(session.session_id);
            sessionsList.appendChild(sessionItem);
        });
    }

    function updateSessionFilters(sessions) {
        const agentFilter = document.getElementById('session-agent-filter');
        const userFilter = document.getElementById('session-user-filter');
        if (!agentFilter || !userFilter) return;

        const currentAgentFilter = agentFilter.value;
        const currentUserFilter = userFilter.value;

        // Clear options
        agentFilter.innerHTML = '<option value="">All Agents</option>';
        userFilter.innerHTML = '<option value="">All Users</option>';

        const agentIds = [...new Set(sessions.map(s => s.agent_id))];
        const userIds = [...new Set(sessions.map(s => s.user_id))];

        agentIds.forEach(id => agentFilter.add(new Option(id, id)));
        userIds.forEach(id => userFilter.add(new Option(id, id)));

        agentFilter.value = currentAgentFilter;
        userFilter.value = currentUserFilter;
    }

    async function updateDashboard() {
        const sessions = await fetchSessions();
        if (agentCountElement) agentCountElement.textContent = (await fetchWithAuth('/agents/').then(res => res.json())).length;
        if (sessionCountElement) sessionCountElement.textContent = sessions.length;
        addActivity(`Dashboard updated with ${sessions.length} sessions.`);
    }

    // --- MODAL FUNCTIONS ---
    function createToolItemElement(tool = {}) {
        const toolItem = document.createElement('div');
        toolItem.className = 'tool-item';
        
        const toolId = tool.toolId || `tool_${crypto.randomUUID()}`;
        
        toolItem.innerHTML = `
            <div class="tool-item-header">
                <h4>${tool.name || 'New Tool'}</h4>
                <button type="button" class="btn-icon remove-tool-btn"><span class="material-icons">delete</span></button>
            </div>
            <div class="tool-item-body">
                <input type="hidden" class="tool-id" value="${toolId}">
                <div class="form-group">
                    <label>Tool Name</label>
                    <input type="text" class="tool-name" value="${tool.name || ''}" required>
                </div>
                <div class="form-group">
                    <label>Tool Type</label>
                    <select class="tool-type">
                        <option value="api" ${tool.type === 'api' ? 'selected' : ''}>API</option>
                        <option value="function" ${tool.type === 'function' ? 'selected' : ''}>Function</option>
                        <option value="database" ${tool.type === 'database' ? 'selected' : ''}>Database</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Description</label>
                    <textarea class="tool-description" rows="2" required>${tool.description || ''}</textarea>
                </div>
            </div>
        `;
        
        toolItem.querySelector('.remove-tool-btn').addEventListener('click', () => {
            toolItem.remove();
        });

        toolItem.querySelector('.tool-name').addEventListener('input', (e) => {
            toolItem.querySelector('h4').textContent = e.target.value || 'New Tool';
        });
        
        return toolItem;
    }

    function openAgentEditModal(agent) {
        document.getElementById('edit-agent-id').value = agent.agentId;
        document.getElementById('edit-agent-name').value = agent.agentName;
        document.getElementById('edit-agent-system-prompt').value = agent.systemPrompt;
        document.getElementById('edit-agent-llm-provider').value = agent.llmConfig?.provider || 'openai';
        document.getElementById('edit-agent-llm-model').value = agent.llmConfig?.model || 'gpt-4';

        const toolsList = document.getElementById('edit-agent-tools-list');
        toolsList.innerHTML = ''; // Clear existing tools
        if (agent.tools && agent.tools.length > 0) {
            agent.tools.forEach(tool => {
                const toolItem = createToolItemElement(tool);
                toolsList.appendChild(toolItem);
            });
        }

        agentEditModal.style.display = 'block';
    }

    async function viewSessionDetails(sessionId) {
        try {
            const response = await fetchWithAuth(`/sessions/${sessionId}`);
            const details = await response.json();
            document.getElementById('detail-session-id').textContent = details.session_id;
            document.getElementById('detail-agent-name').textContent = details.agent_id;
            document.getElementById('detail-user-id').textContent = details.user_id;
            document.getElementById('detail-created-at').textContent = new Date(details.created_at).toLocaleString();
            document.getElementById('detail-last-activity').textContent = new Date(details.last_activity).toLocaleString();
            document.getElementById('detail-context').textContent = JSON.stringify(details.context, null, 2);
            const historyContainer = document.getElementById('detail-conversation-history');
            historyContainer.innerHTML = '';
            details.history.forEach(msg => {
                const msgEl = document.createElement('div');
                msgEl.className = `message ${msg.type}-message`;
                msgEl.textContent = `[${new Date(msg.timestamp).toLocaleTimeString()}] ${msg.type.toUpperCase()}: ${msg.content}`;
                historyContainer.appendChild(msgEl);
            });
            sessionDetailModal.style.display = 'block';
        } catch (error) {
            console.error('Error fetching session details:', error);
            alert('Could not load session details.');
        }
    }

    // --- CHAT FUNCTIONS ---
    function initChat() {
        chatMessages.innerHTML = '';
        addMessage('bot', 'Hello! I\'m the Master Agent. What would you like to name your new agent?');
        conversationData = { conversation_id: '', messages: [{ role: 'assistant', content: 'Hello! I\'m the Master Agent. What would you like to name your new agent?' }] };
    }

    function addMessage(role, content) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', `${role}-message`);
        messageElement.textContent = content;
        chatMessages.appendChild(messageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function addActivity(message) {
        if (!activityList) return;
        const emptyState = activityList.querySelector('.empty-state');
        if (emptyState) emptyState.remove();
        const activityItem = document.createElement('div');
        activityItem.className = 'activity-item';
        activityItem.innerHTML = `<span class="material-icons">info</span> <p>${message}</p> <span>${new Date().toLocaleTimeString()}</span>`;
        activityList.prepend(activityItem);
    }

    // --- EVENT LISTENERS ---
    navItems.forEach(item => {
        item.addEventListener('click', function() {
            const targetSection = this.getAttribute('data-section');
            navItems.forEach(nav => nav.classList.remove('active'));
            this.classList.add('active');
            sections.forEach(section => section.classList.toggle('active', section.id === targetSection));
            
            if (targetSection === 'my-agents') fetchAgents();
            else if (targetSection === 'create-agent' && chatMessages.children.length === 0) initChat();
            else if (targetSection === 'dashboard') updateDashboard();
            else if (targetSection === 'settings') loadApiKeys();
            else if (targetSection === 'sessions') fetchSessions();
        });
    });

    loginForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        loginError.textContent = '';
        const formData = new FormData(loginForm);
        try {
            const response = await fetch('/token', { 
                method: 'POST', 
                body: new URLSearchParams(formData)
            });
            const data = await response.json();
            if (response.ok) {
                localStorage.setItem('accessToken', data.access_token);
                showApp();
            } else {
                loginError.textContent = data.detail || 'Login failed';
            }
        } catch (error) {
            loginError.textContent = 'An error occurred. Please try again.';
        }
    });

    registerForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        registerError.textContent = '';
        const user = Object.fromEntries(new FormData(registerForm));
        try {
            const response = await fetch('/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(user)
            });
            const data = await response.json();
            if (response.ok) {
                alert('Registration successful! Please login.');
                showLoginForm();
            } else {
                registerError.textContent = data.detail || 'Registration failed';
            }
        } catch (error) {
            registerError.textContent = 'An error occurred. Please try again.';
        }
    });

    chatForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        const userMessage = messageInput.value.trim();
        if (!userMessage) return;

        addMessage('user', userMessage);
        messageInput.value = '';

        try {
            const response = await fetchWithAuth('/master-agent/conversation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: userMessage, conversation_id: conversationData.conversation_id })
            });
            const data = await response.json();
            if (response.ok) {
                conversationData = data;
                const lastMessage = data.messages[data.messages.length - 1];
                if (lastMessage?.role === 'assistant') addMessage('bot', lastMessage.content);
                if (data.completed) {
                    fetchAgents();
                    updateDashboard();
                    const agentName = data.messages.find(m => m.content.includes('created successfully'))?.content.match(/Agent '([^']+)'/)?.[1] || 'New agent';
                    addActivity(`Agent "${agentName}" was created`);
                }
            } else {
                addMessage('bot', `Error: ${data.detail || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Error sending message:', error);
            addMessage('bot', 'Sorry, an error occurred.');
        }
    });

    document.getElementById('add-tool-btn').addEventListener('click', () => {
        const toolsList = document.getElementById('edit-agent-tools-list');
        const newTool = createToolItemElement();
        toolsList.appendChild(newTool);
    });

    editAgentForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        const agentId = document.getElementById('edit-agent-id').value;

        const tools = [];
        document.querySelectorAll('#edit-agent-tools-list .tool-item').forEach(item => {
            const toolName = item.querySelector('.tool-name').value;
            if (toolName) { // Only add tools that have a name
                tools.push({
                    toolId: item.querySelector('.tool-id').value,
                    name: toolName,
                    type: item.querySelector('.tool-type').value,
                    description: item.querySelector('.tool-description').value,
                    schema: {} // Placeholder for schema
                });
            }
        });

        const agentData = {
            agentName: document.getElementById('edit-agent-name').value,
            systemPrompt: document.getElementById('edit-agent-system-prompt').value,
            llmConfig: {
                provider: document.getElementById('edit-agent-llm-provider').value,
                model: document.getElementById('edit-agent-llm-model').value
            },
            tools: tools
        };

        try {
            const response = await fetchWithAuth(`/agents/${agentId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(agentData)
            });
            if (response.ok) {
                agentEditModal.style.display = 'none';
                fetchAgents();
                addActivity(`Agent ${agentData.agentName} updated successfully.`);
            } else {
                const error = await response.json();
                alert(`Error updating agent: ${error.detail}`);
            }
        } catch (error) {
            console.error('Error updating agent:', error);
            alert('An error occurred while updating the agent.');
        }
    });

    deleteAgentBtn.addEventListener('click', async function() {
        const agentId = document.getElementById('edit-agent-id').value;
        if (confirm('Are you sure you want to delete this agent?')) {
            try {
                const response = await fetchWithAuth(`/agents/${agentId}`, { method: 'DELETE' });
                if (response.ok) {
                    agentEditModal.style.display = 'none';
                    fetchAgents();
                    addActivity(`Agent with ID ${agentId.substring(0,8)}... deleted.`);
                } else {
                    const error = await response.json();
                    alert(`Error deleting agent: ${error.detail}`);
                }
            } catch (error) {
                console.error('Error deleting agent:', error);
                alert('An error occurred while deleting the agent.');
            }
        }
    });

    function showLoginForm() {
        loginForm.style.display = 'block';
        registerForm.style.display = 'none';
        loginError.textContent = '';
        registerError.textContent = '';
    }

    function showRegisterForm() {
        loginForm.style.display = 'none';
        registerForm.style.display = 'block';
        loginError.textContent = '';
        registerError.textContent = '';
    }

    showRegister.addEventListener('click', (e) => { e.preventDefault(); showRegisterForm(); });
    showLogin.addEventListener('click', (e) => { e.preventDefault(); showLoginForm(); });
    logoutBtn.addEventListener('click', logout);
    closeModalButtons.forEach(button => button.addEventListener('click', () => {
        agentEditModal.style.display = 'none';
        sessionDetailModal.style.display = 'none';
    }));

    // Initial Load
    checkAuth();
});
    
    // Update session activity chart
    function updateSessionActivityChart(sessions) {
        const chartContainer = document.getElementById('session-activity-chart');
        if (!chartContainer) return;
        
        // Clear previous content
        chartContainer.innerHTML = '';
        
        if (sessions.length === 0) {
            chartContainer.innerHTML = '<p class="empty-state">No session data available</p>';
            return;
        }
        
        // Group sessions by date
        const sessionsByDate = {};
        sessions.forEach(session => {
            const date = new Date(session.created_at || session.last_activity);
            const dateKey = date.toISOString().split('T')[0];
            sessionsByDate[dateKey] = (sessionsByDate[dateKey] || 0) + 1;
        });
        
        // Create a simple line chart
        const chart = document.createElement('div');
        chart.className = 'line-chart';
        
        const chartLine = document.createElement('div');
        chartLine.className = 'chart-line';
        
        // Sort dates
        const sortedDates = Object.keys(sessionsByDate).sort();
        
        sortedDates.forEach((date, index) => {
            const point = document.createElement('div');
            point.className = 'chart-point';
            point.style.left = `${(index / (sortedDates.length - 1 || 1)) * 100}%`;
            point.style.bottom = `${Math.min(90, sessionsByDate[date] * 10)}%`;
            point.title = `${date}: ${sessionsByDate[date]} sessions`;
            
            chartLine.appendChild(point);
        });
        
        chart.appendChild(chartLine);
        
        // Add date labels
        if (sortedDates.length > 1) {
            const labels = document.createElement('div');
            labels.className = 'chart-labels';
            
            [sortedDates[0], sortedDates[sortedDates.length - 1]].forEach((date, index) => {
                const label = document.createElement('div');
                label.className = 'chart-label';
                label.style.left = index === 0 ? '0%' : '100%';
                label.style.transform = index === 0 ? 'translateX(0)' : 'translateX(-100%)';
                label.textContent = date;
                labels.appendChild(label);
            });
            
            chart.appendChild(labels);
        }
        
        chartContainer.appendChild(chart);
    }
    
    // Initialize dashboard on page load
    updateDashboard();
    
    // Modal functionality
    closeModalButtons.forEach(button => {
        button.addEventListener('click', () => {
            const modal = button.closest('.modal');
            if (modal) {
                modal.style.display = 'none';
            }
        });
    });
    
    // Close modal when clicking outside of modal content
    window.addEventListener('click', (event) => {
        if (event.target === agentEditModal) {
            agentEditModal.style.display = 'none';
        }
        if (event.target === sessionDetailModal) {
            sessionDetailModal.style.display = 'none';
        }
    });
    
    // Open agent edit modal
    function openAgentEditModal(agent) {
        // Populate form fields with agent data
        document.getElementById('edit-agent-id').value = agent.agentId;
        document.getElementById('edit-agent-name').value = agent.agentName || '';
        document.getElementById('edit-agent-system-prompt').value = agent.systemPrompt || '';
        
        const providerSelect = document.getElementById('edit-agent-llm-provider');
        const modelSelect = document.getElementById('edit-agent-llm-model');
        
        if (agent.llmConfig) {
            // Set provider and model if available
            if (agent.llmConfig.provider) {
                providerSelect.value = agent.llmConfig.provider;
            }
            
            if (agent.llmConfig.model) {
                modelSelect.value = agent.llmConfig.model;
            }
        }
        
        // Display the modal
        agentEditModal.style.display = 'block';
    }
    
    // Handle edit agent form submission
    editAgentForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        
        const agentId = document.getElementById('edit-agent-id').value;
        const agentName = document.getElementById('edit-agent-name').value;
        const systemPrompt = document.getElementById('edit-agent-system-prompt').value;
        const provider = document.getElementById('edit-agent-llm-provider').value;
        const model = document.getElementById('edit-agent-llm-model').value;
        
        try {
            const response = await fetch(`/agents/${agentId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    agentId: agentId,
                    agentName: agentName,
                    systemPrompt: systemPrompt,
                    llmConfig: {
                        provider: provider,
                        model: model
                    },
                    version: "1.0",  // Required fields for API compatibility
                    dataSchema: {},
                    tools: [],
                    workflows: [],
                    schedules: []
                })
            });
            
            if (response.ok) {
                // Update successful
                agentEditModal.style.display = 'none';
                fetchAgents(); // Refresh the agents list
                addActivity(`Agent "${agentName}" was updated`);
            } else {
                alert('Failed to update agent. Please try again.');
            }
        } catch (error) {
            console.error('Error updating agent:', error);
            alert('An error occurred while updating the agent.');
        }
    });
    
    // Handle agent deletion
    deleteAgentBtn.addEventListener('click', async function() {
        const agentId = document.getElementById('edit-agent-id').value;
        const agentName = document.getElementById('edit-agent-name').value;
        
        if (confirm(`Are you sure you want to delete agent "${agentName}"?`)) {
            try {
                const response = await fetch(`/agents/${agentId}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    // Deletion successful
                    agentEditModal.style.display = 'none';
                    fetchAgents(); // Refresh the agents list
                    addActivity(`Agent "${agentName}" was deleted`);
                } else {
                    alert('Failed to delete agent. Please try again.');
                }
            } catch (error) {
                console.error('Error deleting agent:', error);
                alert('An error occurred while deleting the agent.');
            }
        }
    });
