class Dashboard {
    constructor() {
        this.authService = authService;
        this.questions = [];
        this.subscriptionData = null;
        this.currentSection = 'questions';
        this.editingQuestionId = null;
        this.init();
    }

    async init() {
        try {
            await this.loadQuestions();
            await this.loadSubscriptionInfo();
            this.setupEventListeners();
            this.loadUserProfile();
            this.showSection('questions');
        } catch (error) {
            console.error('Dashboard initialization failed:', error);
            this.showNotification('Failed to initialize dashboard. Please refresh the page.', 'error');
        }
    }

    // SECTION MANAGEMENT
    showSection(sectionName) {
        // Hide all sections
        const sections = ['questions', 'employees', 'subscription', 'settings'];
        sections.forEach(section => {
            const element = document.getElementById(`${section}-section`);
            if (element) {
                element.style.display = 'none';
            }
        });

        // Remove active class from all sidebar links
        document.querySelectorAll('.sidebar-nav a').forEach(link => {
            link.classList.remove('active');
        });

        // Show selected section
        const selectedSection = document.getElementById(`${sectionName}-section`);
        if (selectedSection) {
            selectedSection.style.display = 'block';
        }

        // Add active class to clicked link
        const activeLink = document.querySelector(`[data-section="${sectionName}"]`);
        if (activeLink) {
            activeLink.classList.add('active');
        }

        this.currentSection = sectionName;
    }

    setupEventListeners() {
        // Add question form
        const addForm = document.getElementById('addQuestionForm');
        if (addForm) {
            addForm.addEventListener('submit', (e) => {
                e.preventDefault();
                const question = document.getElementById('newQuestion').value;
                const answer = document.getElementById('newAnswer').value;
                
                if (question && answer) {
                    this.addQuestion(question, answer);
                } else {
                    this.showNotification('Please fill both question and answer fields', 'error');
                }
            });
        }

        // Edit question form
        const editForm = document.getElementById('editQuestionForm');
        if (editForm) {
            editForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveEditedQuestion();
            });
        }

        // Generate script button
        const generateScriptBtn = document.getElementById('generateScript');
        if (generateScriptBtn) {
            generateScriptBtn.addEventListener('click', () => {
                this.generateScript();
            });
        }

        // Sidebar navigation
        document.querySelectorAll('.sidebar-nav a').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const section = link.getAttribute('data-section');
                if (section) {
                    this.showSection(section);
                }
            });
        });

        // Logout button
        const logoutBtn = document.querySelector('.logout-btn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => {
                this.authService.logout();
            });
        }
    }

    // QUESTION MANAGEMENT
    async loadQuestions() {
        try {
            const response = await fetch(`${API_BASE_URL}/questions`, {
                headers: this.authService.getAuthHeaders()
            });

            if (response.status === 401) {
                this.showNotification('Session expired. Please login again.', 'error');
                this.authService.logout();
                return;
            }

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `Failed to load questions: ${response.status}`);
            }

            this.questions = await response.json();
            this.renderQuestions();
            
        } catch (error) {
            console.error('Error loading questions:', error);
            
            if (error.message.includes('Authentication required') || 
                error.message.includes('401')) {
                this.showNotification('Your session has expired. Redirecting to login...', 'error');
                setTimeout(() => {
                    this.authService.logout();
                }, 2000);
            } else {
                this.showNotification('Failed to load questions: ' + error.message, 'error');
            }
        }
    }

    renderQuestions() {
        const container = document.getElementById('questionsList');
        if (!container) {
            console.error('Questions list container not found');
            return;
        }

        if (this.questions.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-question-circle"></i>
                    <h3>No Questions Yet</h3>
                    <p>Add your first question to get started!</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.questions.map(question => `
            <div class="question-item" id="question-${question._id}">
                <div class="question-header">
                    <div class="question-text">${this.escapeHtml(question.question)}</div>
                    <div class="question-actions">
                        <button class="btn-edit" onclick="dashboard.openEditModal('${question._id}')">
                            <i class="fas fa-edit"></i> Edit
                        </button>
                        <button class="btn-delete" onclick="dashboard.deleteQuestion('${question._id}')">
                            <i class="fas fa-trash"></i> Delete
                        </button>
                    </div>
                </div>
                <div class="answer-text">${this.escapeHtml(question.answer)}</div>
                <div class="question-meta">
                    <small>Created: ${this.formatDate(question.created_at)}</small>
                    <small>Updated: ${this.formatDate(question.updated_at)}</small>
                </div>
            </div>
        `).join('');
    }

    // MODAL EDITING
    openEditModal(questionId) {
        const question = this.questions.find(q => q._id === questionId);
        if (!question) {
            this.showNotification('Question not found', 'error');
            return;
        }

        this.editingQuestionId = questionId;
        
        // Fill the modal form
        document.getElementById('editQuestion').value = question.question;
        document.getElementById('editAnswer').value = question.answer;
        
        // Show modal
        document.getElementById('editQuestionModal').style.display = 'flex';
    }

    closeEditModal() {
        document.getElementById('editQuestionModal').style.display = 'none';
        this.editingQuestionId = null;
    }

    async saveEditedQuestion() {
        if (!this.editingQuestionId) return;

        const question = document.getElementById('editQuestion').value.trim();
        const answer = document.getElementById('editAnswer').value.trim();

        if (!question || !answer) {
            this.showNotification('Please fill both question and answer fields', 'error');
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/questions/${this.editingQuestionId}`, {
                method: 'PUT',
                headers: this.authService.getAuthHeaders(),
                body: JSON.stringify({ 
                    question: question, 
                    answer: answer 
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to update question');
            }

            await this.loadQuestions();
            this.closeEditModal();
            this.showNotification('Question updated successfully!', 'success');
            
        } catch (error) {
            console.error('Error updating question:', error);
            this.showNotification('Failed to update question: ' + error.message, 'error');
        }
    }

    async addQuestion(question, answer) {
        try {
            // Validate inputs
            if (!question || !question.trim()) {
                this.showNotification('Question is required', 'error');
                return;
            }
            if (!answer || !answer.trim()) {
                this.showNotification('Answer is required', 'error');
                return;
            }

            // Check subscription limits
            if (this.subscriptionData && 
                this.subscriptionData.questions_used >= this.subscriptionData.questions_allowed) {
                this.showNotification('Question limit reached. Please upgrade your plan.', 'error');
                return;
            }

            const response = await fetch(`${API_BASE_URL}/questions`, {
                method: 'POST',
                headers: this.authService.getAuthHeaders(),
                body: JSON.stringify({ 
                    question: question.trim(), 
                    answer: answer.trim() 
                })
            });

            if (response.status === 401) {
                this.showNotification('Session expired. Please login again.', 'error');
                this.authService.logout();
                return;
            }

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to add question');
            }

            await this.loadQuestions();
            await this.loadSubscriptionInfo();
            this.clearForm();
            this.showNotification('Question added successfully!', 'success');
            
        } catch (error) {
            console.error('Error adding question:', error);
            
            if (error.message.includes('Authentication required') || 
                error.message.includes('401')) {
                this.showNotification('Your session has expired. Please login again.', 'error');
                this.authService.logout();
            } else {
                this.showNotification('Failed to add question: ' + error.message, 'error');
            }
        }
    }

    async deleteQuestion(questionId) {
        try {
            if (!confirm('Are you sure you want to delete this question?')) {
                return;
            }

            const response = await fetch(`${API_BASE_URL}/questions/${questionId}`, {
                method: 'DELETE',
                headers: this.authService.getAuthHeaders()
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to delete question');
            }

            await this.loadQuestions();
            await this.loadSubscriptionInfo();
            this.showNotification('Question deleted successfully!', 'success');
        } catch (error) {
            console.error('Error deleting question:', error);
            this.showNotification('Failed to delete question: ' + error.message, 'error');
        }
    }

    // SUBSCRIPTION MANAGEMENT
    async loadSubscriptionInfo() {
        try {
            const response = await fetch(`${API_BASE_URL}/subscription/status`, {
                headers: this.authService.getAuthHeaders()
            });

            if (response.status === 401) {
                this.showNotification('Session expired. Please login again.', 'error');
                this.authService.logout();
                return;
            }

            if (!response.ok) {
                throw new Error(`Failed to load subscription info: ${response.status}`);
            }

            this.subscriptionData = await response.json();
            this.renderSubscriptionInfo();
            
        } catch (error) {
            console.error('Error loading subscription info:', error);
        }
    }

    renderSubscriptionInfo() {
        const container = document.getElementById('subscriptionInfo');
        if (!container || !this.subscriptionData) return;

        const { plan, start_date, end_date, questions_allowed, questions_used, is_trial, is_expired } = this.subscriptionData;
        
        const planNames = {
            'trial': 'Free Trial',
            'monthly': 'Monthly Plan',
            'quarterly': 'Quarterly Plan', 
            'yearly': 'Yearly Plan'
        };

        const planColors = {
            'trial': '#f59e0b',
            'monthly': '#6366f1',
            'quarterly': '#10b981',
            'yearly': '#8b5cf6'
        };

        const endDate = new Date(end_date);
        const now = new Date();
        const daysLeft = Math.ceil((endDate - now) / (1000 * 60 * 60 * 24));
        
        const status = is_expired ? 'Expired' : 
                      is_trial ? 'Trial' : 'Active';

        const statusColor = is_expired ? '#ef4444' : 
                           is_trial ? '#f59e0b' : '#10b981';

        container.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap;">
                <div>
                    <h3 style="margin: 0 0 10px 0;">${planNames[plan] || plan}</h3>
                    <p style="margin: 0; opacity: 0.9;">Status: <span style="color: ${statusColor}; font-weight: bold;">${status}</span></p>
                    <p style="margin: 5px 0; opacity: 0.9;">
                        ${is_expired ? 'Expired on' : is_trial ? 'Trial ends in' : 'Renews in'} 
                        <strong>${daysLeft} days</strong>
                    </p>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 1.5rem; font-weight: bold; color: ${planColors[plan] || '#6366f1'};">
                        ${questions_used}/${questions_allowed}
                    </div>
                    <div style="font-size: 0.9rem; opacity: 0.9;">Questions Used</div>
                </div>
            </div>
        `;

        // Also update subscription details section
        const subscriptionDetails = document.getElementById('subscriptionDetails');
        if (subscriptionDetails) {
            subscriptionDetails.innerHTML = `
                <h3>Current Plan: ${planNames[plan] || plan}</h3>
                <div class="plan-details">
                    <div class="plan-detail">
                        <div class="value" style="color: ${statusColor};">${status}</div>
                        <div class="label">Status</div>
                    </div>
                    <div class="plan-detail">
                        <div class="value">${questions_used}/${questions_allowed}</div>
                        <div class="label">Questions Used</div>
                    </div>
                    <div class="plan-detail">
                        <div class="value">${daysLeft}</div>
                        <div class="label">Days ${is_expired ? 'Since Expired' : 'Remaining'}</div>
                    </div>
                    <div class="plan-detail">
                        <div class="value">${this.formatDate(end_date)}</div>
                        <div class="label">${is_expired ? 'Expired On' : 'Renews On'}</div>
                    </div>
                </div>
            `;
        }
    }

    // UTILITY METHODS
    loadUserProfile() {
        const welcomeElement = document.getElementById('welcomeUser');
        if (welcomeElement) {
            const userName = localStorage.getItem('userName') || 'User';
            welcomeElement.textContent = `Welcome, ${userName}!`;
        }
    }

    generateScript() {
        try {
            const website = this.subscriptionData?.website || 
                           localStorage.getItem('userWebsite') || 
                           'example.com';
            
            const scriptCode = `
<script src="${window.location.origin}/speechbot/speechbot.js"></script>
<script>
    SpeechBot.init('${website}');
</script>
            `.trim();

            const scriptCodeElement = document.getElementById('scriptCode');
            const scriptSection = document.getElementById('scriptSection');
            
            if (scriptCodeElement && scriptSection) {
                scriptCodeElement.textContent = scriptCode;
                scriptSection.style.display = 'block';
                this.showNotification('Script generated successfully!', 'success');
            }
        } catch (error) {
            console.error('Error generating script:', error);
            this.showNotification('Failed to generate script', 'error');
        }
    }

    showNotification(message, type = 'info') {
        // Remove existing notification
        const existingNotification = document.querySelector('.dashboard-notification');
        if (existingNotification) {
            existingNotification.remove();
        }

        // Create notification element
        const notification = document.createElement('div');
        notification.className = `dashboard-notification dashboard-notification-${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <span class="notification-message">${message}</span>
                <button class="notification-close">&times;</button>
            </div>
        `;

        // Add to page
        document.body.appendChild(notification);

        // Auto remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);

        // Close button event
        notification.querySelector('.notification-close').addEventListener('click', () => {
            notification.remove();
        });
    }

    formatDate(dateString) {
        if (!dateString) return 'Unknown';
        return new Date(dateString).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }

    clearForm() {
        const questionInput = document.getElementById('newQuestion');
        const answerInput = document.getElementById('newAnswer');
        
        if (questionInput) questionInput.value = '';
        if (answerInput) answerInput.value = '';
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
}

// Payment Handler Class
class PaymentHandler {
    constructor() {
        this.razorpayOptions = {
            key: 'rzp_test_YOUR_KEY_ID', // Replace with your actual Razorpay key
            name: 'SpeechBot',
            description: 'Subscription Payment',
            theme: {
                color: '#6366f1'
            }
        };
    }

    async initiateSubscription(plan) {
        try {
            const response = await fetch(`${API_BASE_URL}/subscription/create-order`, {
                method: 'POST',
                headers: authService.getAuthHeaders(),
                body: JSON.stringify({ plan })
            });

            if (!response.ok) {
                throw new Error('Failed to create order');
            }

            const order = await response.json();

            const options = {
                ...this.razorpayOptions,
                amount: order.amount,
                currency: order.currency,
                order_id: order.id,
                handler: async (response) => {
                    await this.handlePaymentSuccess(response, plan, order.amount);
                },
                prefill: {
                    name: 'Customer Name',
                    email: 'customer@example.com',
                }
            };

            const rzp = new Razorpay(options);
            rzp.open();

        } catch (error) {
            console.error('Payment initiation error:', error);
            dashboard.showNotification('Failed to initiate payment: ' + error.message, 'error');
        }
    }

    async handlePaymentSuccess(paymentResponse, plan, amount) {
        try {
            const verificationData = {
                razorpay_payment_id: paymentResponse.razorpay_payment_id,
                razorpay_order_id: paymentResponse.razorpay_order_id,
                razorpay_signature: paymentResponse.razorpay_signature,
                plan: plan,
                amount: amount
            };

            const response = await fetch(`${API_BASE_URL}/subscription/verify`, {
                method: 'POST',
                headers: authService.getAuthHeaders(),
                body: JSON.stringify(verificationData)
            });

            if (!response.ok) {
                throw new Error('Payment verification failed');
            }

            const result = await response.json();
            dashboard.showNotification('Payment successful! Subscription activated.', 'success');
            
            setTimeout(() => {
                window.location.reload();
            }, 2000);

        } catch (error) {
            console.error('Payment verification error:', error);
            dashboard.showNotification('Payment verification failed: ' + error.message, 'error');
        }
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (authService.isAuthenticated() && authService.getUserType() !== 'admin') {
        window.dashboard = new Dashboard();
        window.paymentHandler = new PaymentHandler();
    } else if (!authService.isAuthenticated()) {
        window.location.href = 'login.html';
    }
});

// Copy script function
function copyScript() {
    const scriptCode = document.getElementById('scriptCode');
    if (!scriptCode) return;

    const range = document.createRange();
    range.selectNode(scriptCode);
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
    
    try {
        document.execCommand('copy');
        window.getSelection().removeAllRanges();
        dashboard.showNotification('Script copied to clipboard!', 'success');
    } catch (error) {
        console.error('Failed to copy script:', error);
        dashboard.showNotification('Failed to copy script. Please select and copy manually.', 'error');
    }
}

// Close modal when clicking outside
document.addEventListener('click', function(event) {
    const modal = document.getElementById('editQuestionModal');
    if (event.target === modal) {
        dashboard.closeEditModal();
    }
});