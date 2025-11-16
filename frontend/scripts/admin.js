class AdminDashboard {
    constructor() {
        this.authService = authService;
        this.currentTab = 'overview';
        this.init();
    }

    async init() {
        if (!this.authService.isAuthenticated() || this.authService.getUserType() !== 'admin') {
            window.location.href = 'login.html';
            return;
        }

        this.setupEventListeners();
        await this.loadOverview();
        this.showTab('overview');
    }

    setupEventListeners() {
        // Tab navigation
        document.querySelectorAll('.sidebar-nav a').forEach(tab => {
            tab.addEventListener('click', (e) => {
                e.preventDefault();
                const tabName = tab.getAttribute('data-tab');
                this.showTab(tabName);
            });
        });

        // Search functionality
        document.getElementById('clientSearch')?.addEventListener('input', (e) => {
            this.filterClients(e.target.value);
        });

        document.getElementById('employeeSearch')?.addEventListener('input', (e) => {
            this.filterEmployees(e.target.value);
        });

        document.getElementById('questionSearch')?.addEventListener('input', (e) => {
            this.filterQuestions(e.target.value);
        });

        document.getElementById('subscriptionSearch')?.addEventListener('input', (e) => {
            this.filterSubscriptions(e.target.value);
        });

        document.getElementById('logSearch')?.addEventListener('input', (e) => {
            this.filterLogs(e.target.value);
        });

        // Filter changes
        document.getElementById('clientFilter')?.addEventListener('change', (e) => {
            this.loadClients();
        });

        document.getElementById('employeeFilter')?.addEventListener('change', (e) => {
            this.loadEmployees();
        });
    }

    showTab(tabName) {
        // Hide all tabs
        document.querySelectorAll('.tab-content').forEach(tab => {
            tab.classList.remove('active');
        });

        // Remove active class from all nav items
        document.querySelectorAll('.sidebar-nav a').forEach(nav => {
            nav.classList.remove('active');
        });

        // Show selected tab
        document.getElementById(`${tabName}-tab`).classList.add('active');
        
        // Add active class to clicked nav item
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

        this.currentTab = tabName;

        // Load tab data
        switch(tabName) {
            case 'overview':
                this.loadOverview();
                break;
            case 'clients':
                this.loadClients();
                break;
            case 'employees':
                this.loadEmployees();
                break;
            case 'questions':
                this.loadAllQuestions();
                break;
            case 'subscriptions':
                this.loadSubscriptions();
                break;
            case 'logs':
                this.loadSystemLogs();
                break;
        }
    }

    async loadOverview() {
        try {
            // Load stats
            const [clients, employees, questions, subscriptions] = await Promise.all([
                this.fetchData('/admin/clients'),
                this.fetchData('/admin/employees'),
                this.fetchData('/admin/questions'),
                this.fetchData('/admin/subscriptions')
            ]);

            document.getElementById('totalClients').textContent = clients.length;
            document.getElementById('totalEmployees').textContent = employees.length;
            document.getElementById('totalQuestions').textContent = questions.length;
            document.getElementById('activeSubscriptions').textContent = 
                subscriptions.filter(sub => new Date(sub.end_date) > new Date()).length;

            // Load recent logs
            await this.loadRecentLogs();

        } catch (error) {
            console.error('Error loading overview:', error);
            this.showError('Failed to load overview data');
        }
    }

    async loadRecentLogs() {
        try {
            const logs = await this.fetchData('/admin/logs?limit=10');
            this.renderRecentLogs(logs);
        } catch (error) {
            console.error('Error loading recent logs:', error);
        }
    }

    renderRecentLogs(logs) {
        const container = document.getElementById('recentLogs');
        if (!container) return;

        container.innerHTML = logs.map(log => `
            <div class="log-item">
                <div class="log-header">
                    <span class="log-action">${this.formatAction(log.action)}</span>
                    <span class="log-timestamp">${this.formatDate(log.timestamp)}</span>
                </div>
                <div class="log-details">
                    User: ${log.user_id} | Client: ${log.client_id || 'N/A'}
                </div>
            </div>
        `).join('');
    }

    async loadClients() {
        try {
            const clients = await this.fetchData('/admin/clients');
            this.renderClients(clients);
        } catch (error) {
            console.error('Error loading clients:', error);
            this.showError('Failed to load clients');
        }
    }

    renderClients(clients) {
        const container = document.getElementById('clientsTable');
        if (!container) return;

        const filter = document.getElementById('clientFilter')?.value || 'all';
        const search = document.getElementById('clientSearch')?.value.toLowerCase() || '';

        const filteredClients = clients.filter(client => {
            const matchesSearch = client.name.toLowerCase().includes(search) ||
                                client.email.toLowerCase().includes(search) ||
                                client.website.toLowerCase().includes(search);
            
            const matchesFilter = filter === 'all' || 
                                (filter === 'active' && client.is_active && new Date(client.subscription_end) > new Date()) ||
                                (filter === 'trial' && client.subscription_plan === 'trial') ||
                                (filter === 'expired' && new Date(client.subscription_end) <= new Date());

            return matchesSearch && matchesFilter;
        });

        container.innerHTML = filteredClients.map(client => `
            <tr>
                <td>${this.escapeHtml(client.name)}</td>
                <td>${this.escapeHtml(client.email)}</td>
                <td>${this.escapeHtml(client.website)}</td>
                <td>
                    <span class="badge ${this.getSubscriptionBadgeClass(client.subscription_plan)}">
                        ${client.subscription_plan}
                    </span>
                </td>
                <td>
                    <span class="badge ${client.is_active ? 'badge-success' : 'badge-danger'}">
                        ${client.is_active ? 'Active' : 'Inactive'}
                    </span>
                </td>
                <td>${client.questions_used || 0}/${client.questions_allowed || 0}</td>
                <td class="action-buttons">
                    <button class="btn-sm btn-primary-sm" onclick="admin.viewClient('${client._id}')">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn-sm btn-danger-sm" onclick="admin.deleteClient('${client._id}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
        `).join('');
    }

    async loadEmployees() {
        try {
            const employees = await this.fetchData('/admin/employees');
            this.renderEmployees(employees);
        } catch (error) {
            console.error('Error loading employees:', error);
            this.showError('Failed to load employees');
        }
    }

    async renderEmployees(employees) {
        const container = document.getElementById('employeesTable');
        if (!container) return;

        const filter = document.getElementById('employeeFilter')?.value || 'all';
        const search = document.getElementById('employeeSearch')?.value.toLowerCase() || '';

        const filteredEmployees = employees.filter(employee => {
            const matchesSearch = employee.name.toLowerCase().includes(search) ||
                                employee.email.toLowerCase().includes(search) ||
                                employee.website.toLowerCase().includes(search);
            
            const matchesFilter = filter === 'all' || 
                                (filter === 'active' && employee.is_active) ||
                                (filter === 'inactive' && !employee.is_active);

            return matchesSearch && matchesFilter;
        });

        // Get client names for display
        const clients = await this.fetchData('/admin/clients');
        const clientMap = new Map(clients.map(client => [client._id, client.name]));

        container.innerHTML = filteredEmployees.map(employee => `
            <tr>
                <td>${this.escapeHtml(employee.name)}</td>
                <td>${this.escapeHtml(employee.email)}</td>
                <td>${this.escapeHtml(clientMap.get(employee.client_id) || 'Unknown')}</td>
                <td>${this.escapeHtml(employee.website)}</td>
                <td>
                    <span class="badge ${employee.is_active ? 'badge-success' : 'badge-danger'}">
                        ${employee.is_active ? 'Active' : 'Inactive'}
                    </span>
                </td>
                <td class="action-buttons">
                    <button class="btn-sm btn-primary-sm" onclick="admin.viewEmployee('${employee._id}')">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn-sm btn-danger-sm" onclick="admin.deleteEmployee('${employee._id}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
        `).join('');
    }

    async loadAllQuestions() {
        try {
            const questions = await this.fetchData('/admin/questions');
            this.renderAllQuestions(questions);
        } catch (error) {
            console.error('Error loading questions:', error);
            this.showError('Failed to load questions');
        }
    }

    async renderAllQuestions(questions) {
        const container = document.getElementById('allQuestionsList');
        if (!container) return;

        const search = document.getElementById('questionSearch')?.value.toLowerCase() || '';

        const filteredQuestions = questions.filter(q => 
            q.question.toLowerCase().includes(search) ||
            q.answer.toLowerCase().includes(search)
        );

        // Get client names for display
        const clients = await this.fetchData('/admin/clients');
        const clientMap = new Map(clients.map(client => [client._id, client.name]));

        container.innerHTML = filteredQuestions.map(question => `
            <div class="question-item">
                <div class="question-header">
                    <div class="question-text">${this.escapeHtml(question.question)}</div>
                    <div class="question-actions">
                        <span class="badge badge-info">
                            Client: ${this.escapeHtml(clientMap.get(question.client_id) || 'Unknown')}
                        </span>
                        <button class="btn-edit" onclick="admin.editQuestion('${question._id}')">Edit</button>
                        <button class="btn-delete" onclick="admin.deleteQuestion('${question._id}')">Delete</button>
                    </div>
                </div>
                <div class="answer-text">${this.escapeHtml(question.answer)}</div>
                <div style="margin-top: 10px; font-size: 0.8rem; color: #94a3b8;">
                    Created: ${this.formatDate(question.created_at)} | 
                    Updated: ${this.formatDate(question.updated_at)}
                </div>
            </div>
        `).join('');
    }

    async loadSubscriptions() {
        try {
            const subscriptions = await this.fetchData('/admin/subscriptions');
            this.renderSubscriptions(subscriptions);
        } catch (error) {
            console.error('Error loading subscriptions:', error);
            this.showError('Failed to load subscriptions');
        }
    }

    async renderSubscriptions(subscriptions) {
        const container = document.getElementById('subscriptionsTable');
        if (!container) return;

        const search = document.getElementById('subscriptionSearch')?.value.toLowerCase() || '';
        const filter = document.getElementById('subscriptionFilter')?.value || 'all';

        const filteredSubscriptions = subscriptions.filter(sub => {
            const matchesSearch = sub.razorpay_payment_id.toLowerCase().includes(search);
            
            const now = new Date();
            const endDate = new Date(sub.end_date);
            const matchesFilter = filter === 'all' || 
                                (filter === 'active' && endDate > now) ||
                                (filter === 'expired' && endDate <= now) ||
                                (filter === 'trial' && sub.plan === 'trial');

            return matchesSearch && matchesFilter;
        });

        // Get client names for display
        const clients = await this.fetchData('/admin/clients');
        const clientMap = new Map(clients.map(client => [client._id, client.name]));

        container.innerHTML = filteredSubscriptions.map(sub => {
            const isActive = new Date(sub.end_date) > new Date();
            return `
                <tr>
                    <td>${this.escapeHtml(clientMap.get(sub.client_id) || 'Unknown')}</td>
                    <td>
                        <span class="badge ${this.getSubscriptionBadgeClass(sub.plan)}">
                            ${sub.plan}
                        </span>
                    </td>
                    <td>₹${(sub.amount / 100).toFixed(2)}</td>
                    <td>${this.formatDate(sub.start_date)}</td>
                    <td>${this.formatDate(sub.end_date)}</td>
                    <td>
                        <span class="badge ${isActive ? 'badge-success' : 'badge-danger'}">
                            ${isActive ? 'Active' : 'Expired'}
                        </span>
                    </td>
                    <td>${sub.razorpay_payment_id}</td>
                </tr>
            `;
        }).join('');
    }

    async loadSystemLogs() {
        try {
            const logs = await this.fetchData('/admin/logs');
            this.renderSystemLogs(logs);
        } catch (error) {
            console.error('Error loading system logs:', error);
            this.showError('Failed to load system logs');
        }
    }

    renderSystemLogs(logs) {
        const container = document.getElementById('systemLogs');
        if (!container) return;

        const search = document.getElementById('logSearch')?.value.toLowerCase() || '';
        const filter = document.getElementById('logFilter')?.value || 'all';

        const filteredLogs = logs.filter(log => {
            const matchesSearch = log.action.toLowerCase().includes(search) ||
                                log.user_id.toLowerCase().includes(search);
            
            const matchesFilter = filter === 'all' || 
                                (filter === 'signup' && log.action.includes('signup')) ||
                                (filter === 'question' && log.action.includes('question')) ||
                                (filter === 'subscription' && log.action.includes('subscription'));

            return matchesSearch && matchesFilter;
        });

        container.innerHTML = filteredLogs.map(log => `
            <div class="log-item">
                <div class="log-header">
                    <span class="log-action">${this.formatAction(log.action)}</span>
                    <span class="log-timestamp">${this.formatDate(log.timestamp)}</span>
                </div>
                <div class="log-details">
                    <strong>User:</strong> ${log.user_id} (${log.user_type}) | 
                    <strong>Client:</strong> ${log.client_id || 'N/A'}
                    ${log.details ? `| <strong>Details:</strong> ${JSON.stringify(log.details)}` : ''}
                </div>
            </div>
        `).join('');
    }

    // Filter methods
    filterClients(searchTerm) {
        this.loadClients();
    }

    filterEmployees(searchTerm) {
        this.loadEmployees();
    }

    filterQuestions(searchTerm) {
        this.loadAllQuestions();
    }

    filterSubscriptions(searchTerm) {
        this.loadSubscriptions();
    }

    filterLogs(searchTerm) {
        this.loadSystemLogs();
    }

    // Action methods
    async viewClient(clientId) {
        const client = await this.fetchData(`/admin/clients/${clientId}`);
        alert(`Client Details:\nName: ${client.name}\nEmail: ${client.email}\nWebsite: ${client.website}\nSubscription: ${client.subscription_plan}`);
    }

    async deleteClient(clientId) {
        if (!confirm('Are you sure you want to delete this client? This will also delete all their questions and employees.')) {
            return;
        }

        try {
            await this.fetchData(`/admin/clients/${clientId}`, { method: 'DELETE' });
            this.showSuccess('Client deleted successfully');
            this.loadClients();
            this.loadOverview();
        } catch (error) {
            this.showError('Failed to delete client');
        }
    }

    async viewEmployee(employeeId) {
        const employee = await this.fetchData(`/admin/employees/${employeeId}`);
        alert(`Employee Details:\nName: ${employee.name}\nEmail: ${employee.email}\nWebsite: ${employee.website}`);
    }

    async deleteEmployee(employeeId) {
        if (!confirm('Are you sure you want to delete this employee?')) {
            return;
        }

        try {
            await this.fetchData(`/admin/employees/${employeeId}`, { method: 'DELETE' });
            this.showSuccess('Employee deleted successfully');
            this.loadEmployees();
            this.loadOverview();
        } catch (error) {
            this.showError('Failed to delete employee');
        }
    }

    async editQuestion(questionId) {
        const question = await this.fetchData(`/admin/questions/${questionId}`);
        const newQuestion = prompt('Edit question:', question.question);
        const newAnswer = prompt('Edit answer:', question.answer);

        if (newQuestion && newAnswer) {
            try {
                await this.fetchData(`/admin/questions/${questionId}`, {
                    method: 'PUT',
                    body: JSON.stringify({ question: newQuestion, answer: newAnswer })
                });
                this.showSuccess('Question updated successfully');
                this.loadAllQuestions();
            } catch (error) {
                this.showError('Failed to update question');
            }
        }
    }

    async deleteQuestion(questionId) {
        if (!confirm('Are you sure you want to delete this question?')) {
            return;
        }

        try {
            await this.fetchData(`/admin/questions/${questionId}`, { method: 'DELETE' });
            this.showSuccess('Question deleted successfully');
            this.loadAllQuestions();
            this.loadOverview();
        } catch (error) {
            this.showError('Failed to delete question');
        }
    }

    async saveSettings() {
        const trialDuration = document.getElementById('trialDuration').value;
        const trialQuestions = document.getElementById('trialQuestions').value;

        try {
            await this.fetchData('/admin/settings', {
                method: 'POST',
                body: JSON.stringify({ trialDuration, trialQuestions })
            });
            this.showSuccess('Settings saved successfully');
        } catch (error) {
            this.showError('Failed to save settings');
        }
    }

    async clearOldLogs() {
        if (!confirm('Are you sure you want to clear logs older than 30 days?')) {
            return;
        }

        try {
            await this.fetchData('/admin/logs/clear', { method: 'POST' });
            this.showSuccess('Old logs cleared successfully');
            this.loadSystemLogs();
        } catch (error) {
            this.showError('Failed to clear logs');
        }
    }

    async backupDatabase() {
        try {
            const response = await this.fetchData('/admin/backup', { method: 'POST' });
            this.showSuccess('Backup created successfully');
        } catch (error) {
            this.showError('Failed to create backup');
        }
    }

    // Utility methods
    async fetchData(endpoint, options = {}) {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            headers: this.authService.getAuthHeaders(),
            ...options
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    formatDate(dateString) {
        return new Date(dateString).toLocaleString();
    }

    formatAction(action) {
        return action.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    getSubscriptionBadgeClass(plan) {
        const classes = {
            'trial': 'badge-warning',
            'monthly': 'badge-info',
            'quarterly': 'badge-success',
            'yearly': 'badge-success'
        };
        return classes[plan] || 'badge-info';
    }

    escapeHtml(unsafe) {
        if (!unsafe) return '';
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    showSuccess(message) {
        alert(`Success: ${message}`);
    }

    showError(message) {
        alert(`Error: ${message}`);
    }
}

// Initialize admin dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.admin = new AdminDashboard();
});