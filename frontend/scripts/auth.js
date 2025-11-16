const API_BASE_URL = 'http://localhost:8000';

class AuthService {
    constructor() {
        this.token = localStorage.getItem('token');
        this.userType = localStorage.getItem('userType');
        this.userId = localStorage.getItem('userId');
    }

    async login(email, password) {
        try {
            const response = await fetch(`${API_BASE_URL}/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email, password })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Login failed');
            }

            const data = await response.json();
            this.setToken(data.access_token);
            this.setUserType(data.user_type);
            
            const payload = JSON.parse(atob(data.access_token.split('.')[1]));
            this.setUserId(payload.user_id);
            
            return data;
        } catch (error) {
            console.error('Login error:', error);
            throw error;
        }
    }

    async signup(signupData) {
        try {
            const response = await fetch(`${API_BASE_URL}/signup`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(signupData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Signup failed');
            }

            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Signup error:', error);
            throw error;
        }
    }

    // Profile management methods
    async getProfile() {
        try {
            const response = await fetch(`${API_BASE_URL}/profile`, {
                method: 'GET',
                headers: this.getAuthHeaders()
            });

            if (!response.ok) {
                throw new Error('Failed to fetch profile');
            }

            return await response.json();
        } catch (error) {
            console.error('Profile fetch error:', error);
            throw error;
        }
    }

    async updateProfile(profileData) {
        try {
            const response = await fetch(`${API_BASE_URL}/profile`, {
                method: 'PUT',
                headers: this.getAuthHeaders(),
                body: JSON.stringify(profileData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to update profile');
            }

            return await response.json();
        } catch (error) {
            console.error('Profile update error:', error);
            throw error;
        }
    }

    // Employee management methods
    async createEmployee(employeeData) {
        try {
            const response = await fetch(`${API_BASE_URL}/employees`, {
                method: 'POST',
                headers: this.getAuthHeaders(),
                body: JSON.stringify(employeeData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to create employee');
            }

            return await response.json();
        } catch (error) {
            console.error('Employee creation error:', error);
            throw error;
        }
    }

    async getEmployees() {
        try {
            const response = await fetch(`${API_BASE_URL}/employees`, {
                method: 'GET',
                headers: this.getAuthHeaders()
            });

            if (!response.ok) {
                throw new Error('Failed to fetch employees');
            }

            return await response.json();
        } catch (error) {
            console.error('Employees fetch error:', error);
            throw error;
        }
    }

    async updateEmployee(employeeId, employeeData) {
        try {
            const response = await fetch(`${API_BASE_URL}/employees/${employeeId}`, {
                method: 'PUT',
                headers: this.getAuthHeaders(),
                body: JSON.stringify(employeeData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to update employee');
            }

            return await response.json();
        } catch (error) {
            console.error('Employee update error:', error);
            throw error;
        }
    }

    async deleteEmployee(employeeId) {
        try {
            const response = await fetch(`${API_BASE_URL}/employees/${employeeId}`, {
                method: 'DELETE',
                headers: this.getAuthHeaders()
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to delete employee');
            }

            return await response.json();
        } catch (error) {
            console.error('Employee deletion error:', error);
            throw error;
        }
    }

    setToken(token) {
        this.token = token;
        localStorage.setItem('token', token);
    }

    setUserType(userType) {
        this.userType = userType;
        localStorage.setItem('userType', userType);
    }

    setUserId(userId) {
        this.userId = userId;
        localStorage.setItem('userId', userId);
    }

    getToken() {
        return this.token;
    }

    getUserType() {
        return this.userType;
    }

    getUserId() {
        return this.userId;
    }

    isAuthenticated() {
        if (!this.token) {
            return false;
        }

        try {
            const payload = JSON.parse(atob(this.token.split('.')[1]));
            const expiry = payload.exp * 1000;
            return Date.now() < expiry;
        } catch (error) {
            console.error('Token validation error:', error);
            return false;
        }
    }

    getAuthHeaders() {
        if (!this.isAuthenticated()) {
            console.error('User not authenticated or token expired');
            this.logout();
            throw new Error('Authentication required');
        }

        return {
            'Authorization': `Bearer ${this.token}`,
            'Content-Type': 'application/json'
        };
    }

    logout() {
        this.token = null;
        this.userType = null;
        this.userId = null;
        localStorage.removeItem('token');
        localStorage.removeItem('userType');
        localStorage.removeItem('userId');
        window.location.href = '../index.html';
    }
}

const authService = new AuthService();

// Form handling
document.addEventListener('DOMContentLoaded', function() {
    // Login form
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;

            try {
                const result = await authService.login(email, password);
                
                if (result.user_type === 'admin') {
                    window.location.href = 'admin.html';
                } else {
                    window.location.href = 'dashboard.html';
                }
            } catch (error) {
                showFormError('loginForm', error.message);
            }
        });
    }

    // Signup form
    const signupForm = document.getElementById('signupForm');
    if (signupForm) {
        initializeMultiStepForm();
    }

    // Check authentication on protected pages
    const protectedPages = ['dashboard.html', 'admin.html', 'settings.html', 'employees.html'];
    const currentPage = window.location.pathname.split('/').pop();
    
    if (protectedPages.includes(currentPage) && !authService.isAuthenticated()) {
        window.location.href = 'login.html';
    }

    // Load profile data on settings page
    if (currentPage === 'settings.html' && authService.isAuthenticated()) {
        loadProfileData();
        loadWebsiteUrl(); // This will now work
    }

    // Initialize employees page
    if (currentPage === 'employees.html' && authService.isAuthenticated()) {
        initializeEmployeesPage();
    }

    // Initialize dashboard
    if (currentPage === 'dashboard.html' && authService.isAuthenticated()) {
        initializeDashboard();
    }
});

// Multi-step form for signup - SIMPLIFIED VERSION
function initializeMultiStepForm() {
    const signupForm = document.getElementById('signupForm');
    const steps = document.querySelectorAll('.form-step');
    const nextButtons = document.querySelectorAll('.next-btn');
    const prevButtons = document.querySelectorAll('.prev-btn');
    const progress = document.getElementById('progress');
    const completeBtn = document.querySelector('.btn-success');
    
    let currentStep = 0;

    function showStep(stepIndex) {
        console.log(`Showing step ${stepIndex} of ${steps.length}`);
        steps.forEach((step, index) => {
            step.style.display = index === stepIndex ? 'block' : 'none';
        });
        
        // Update progress bar
        const progressPercentage = ((stepIndex + 1) / steps.length) * 100;
        if (progress) {
            progress.style.width = `${progressPercentage}%`;
        }

        // Show/hide buttons
        if (completeBtn) {
            completeBtn.style.display = stepIndex === steps.length - 1 ? 'inline-block' : 'none';
        }
        
        nextButtons.forEach(btn => {
            btn.style.display = stepIndex === steps.length - 1 ? 'none' : 'inline-block';
        });
    }

    // Next button handlers
    nextButtons.forEach(button => {
        button.addEventListener('click', () => {
            console.log('Next button clicked from step:', currentStep);
            if (validateStep(currentStep)) {
                currentStep++;
                showStep(currentStep);
            }
        });
    });

    // Previous button handlers
    prevButtons.forEach(button => {
        button.addEventListener('click', () => {
            if (currentStep > 0) {
                currentStep--;
                showStep(currentStep);
            }
        });
    });

    // Complete Sign Up button handler
    if (completeBtn) {
        completeBtn.addEventListener('click', async function(e) {
            e.preventDefault();
            console.log('Complete Sign Up button clicked');
            
            if (validateStep(currentStep)) {
                console.log('Validation passed, submitting form...');
                
                // Show loading state
                const originalText = completeBtn.innerHTML;
                completeBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Processing...';
                completeBtn.disabled = true;
                
                try {
                    await submitSignupForm();
                } catch (error) {
                    // Reset button on error
                    completeBtn.innerHTML = originalText;
                    completeBtn.disabled = false;
                    console.error('Signup failed:', error);
                }
            }
        });
    }

    // Prevent default form submission
    if (signupForm) {
        signupForm.addEventListener('submit', function(e) {
            e.preventDefault();
        });
    }

    // Initialize first step
    showStep(currentStep);
}

function validateStep(stepIndex) {
    const steps = document.querySelectorAll('.form-step');
    const currentStep = steps[stepIndex];
    const inputs = currentStep.querySelectorAll('input[required]');
    
    for (let input of inputs) {
        if (!input.value.trim()) {
            const fieldName = input.previousElementSibling?.textContent || input.placeholder || 'this field';
            showNotification(`Please fill in ${fieldName}`, 'error');
            input.focus();
            return false;
        }
        
        // Email validation
        if (input.type === 'email' && input.value) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(input.value)) {
                showNotification('Please enter a valid email address', 'error');
                input.focus();
                return false;
            }
        }
        
        // Password confirmation
        if (input.id === 'confirmPassword') {
            const password = document.getElementById('password').value;
            if (input.value !== password) {
                showNotification('Passwords do not match', 'error');
                input.focus();
                return false;
            }
        }
    }
    
    return true;
}

async function submitSignupForm() {
    const signupData = {
        name: document.getElementById('name').value,
        email: document.getElementById('email').value,
        password: document.getElementById('password').value,
        confirm_password: document.getElementById('confirmPassword').value,
        mobile: document.getElementById('mobile').value,
        website: document.getElementById('website').value,
        business_type: document.getElementById('businessType').value,
        location: document.getElementById('location').value,
        pan: document.getElementById('pan').value,
        tan: document.getElementById('tan').value
    };

    console.log('Submitting signup data:', signupData);

    try {
        const result = await authService.signup(signupData);
        console.log('Signup successful:', result);
        
        // Show success message
        showNotification('Signup successful! Redirecting to login...', 'success');
        
        // Redirect to login after delay
        setTimeout(() => {
            window.location.href = 'login.html';
        }, 2000);
        
    } catch (error) {
        console.error('Signup error:', error);
        showFormError('signupForm', error.message);
        throw error;
    }
}

// Profile management
async function loadProfileData() {
    try {
        const profile = await authService.getProfile();
        
        // Update form fields with profile data
        const fields = {
            'fullName': 'name',
            'email': 'email', 
            'mobile': 'mobile',
            'website': 'website',
            'businessType': 'business_type',
            'location': 'location',
            'pan': 'pan',
            'tan': 'tan'
        };
        
        Object.keys(fields).forEach(fieldId => {
            const element = document.getElementById(fieldId);
            if (element && profile[fields[fieldId]]) {
                element.value = profile[fields[fieldId]];
            }
        });
        
    } catch (error) {
        console.error('Error loading profile:', error);
        showNotification('Error loading profile data', 'error');
    }
}

// Load website URL for script generation - ADD THIS FUNCTION
async function loadWebsiteUrl() {
    try {
        const profile = await authService.getProfile();
        const websiteUrl = profile.website || '';
        
        // Update website URL field
        const websiteUrlInput = document.getElementById('websiteUrl');
        if (websiteUrlInput) {
            websiteUrlInput.value = websiteUrl;
        }
        
        // Update embed script if exists
        const embedScript = document.getElementById('embedScript');
        if (embedScript) {
            embedScript.textContent = `<!-- Chat Widget Script -->
<script>
(function() {
    var script = document.createElement('script');
    script.src = '${websiteUrl}/chat-widget.js';
    script.async = true;
    document.head.appendChild(script);
})();
</script>`;
        }
        
    } catch (error) {
        console.error('Error loading website URL:', error);
        // Don't show error notification as this might not be critical
    }
}

// Script Generation Functions
function copyWebsiteUrl() {
    const websiteUrl = document.getElementById('websiteUrl');
    if (websiteUrl) {
        websiteUrl.select();
        websiteUrl.setSelectionRange(0, 99999);
        document.execCommand('copy');
        showNotification('Website URL copied to clipboard!', 'success');
    }
}

function copyEmbedScript() {
    const embedScript = document.getElementById('embedScript');
    if (embedScript) {
        const range = document.createRange();
        range.selectNode(embedScript);
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(range);
        document.execCommand('copy');
        window.getSelection().removeAllRanges();
        showNotification('Embed code copied to clipboard!', 'success');
    }
}

// Employees management
async function initializeEmployeesPage() {
    await loadEmployees();
    
    const createEmployeeForm = document.getElementById('createEmployeeForm');
    if (createEmployeeForm) {
        createEmployeeForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            await createEmployee();
        });
    }
}

async function loadEmployees() {
    try {
        const employees = await authService.getEmployees();
        displayEmployees(employees);
    } catch (error) {
        console.error('Error loading employees:', error);
        showNotification('Error loading employees', 'error');
    }
}

function displayEmployees(employees) {
    const employeesList = document.getElementById('employeesList');
    if (!employeesList) return;

    if (employees.length === 0) {
        employeesList.innerHTML = '<tr><td colspan="6" class="text-center">No employees found</td></tr>';
        return;
    }

    employeesList.innerHTML = employees.map(employee => `
        <tr>
            <td>${employee.name}</td>
            <td>${employee.email}</td>
            <td>${employee.mobile || 'N/A'}</td>
            <td>${employee.website}</td>
            <td>${employee.is_active ? 'Active' : 'Inactive'}</td>
            <td>
                <button class="btn btn-sm btn-warning edit-employee" data-id="${employee._id}">Edit</button>
                <button class="btn btn-sm btn-danger delete-employee" data-id="${employee._id}">Delete</button>
            </td>
        </tr>
    `).join('');

    // Add event listeners for edit/delete buttons
    document.querySelectorAll('.edit-employee').forEach(button => {
        button.addEventListener('click', (e) => {
            const employeeId = e.target.getAttribute('data-id');
            editEmployee(employeeId);
        });
    });

    document.querySelectorAll('.delete-employee').forEach(button => {
        button.addEventListener('click', async (e) => {
            const employeeId = e.target.getAttribute('data-id');
            await deleteEmployee(employeeId);
        });
    });
}

async function createEmployee() {
    try {
        const employeeData = {
            name: document.getElementById('employeeName').value,
            email: document.getElementById('employeeEmail').value,
            mobile: document.getElementById('employeeMobile').value,
            password: document.getElementById('employeePassword').value
        };

        await authService.createEmployee(employeeData);
        showNotification('Employee created successfully', 'success');
        document.getElementById('createEmployeeForm').reset();
        await loadEmployees();
    } catch (error) {
        console.error('Error creating employee:', error);
        showNotification(error.message, 'error');
    }
}

async function editEmployee(employeeId) {
    const newName = prompt('Enter new name:');
    if (newName) {
        try {
            await authService.updateEmployee(employeeId, { name: newName });
            showNotification('Employee updated successfully', 'success');
            await loadEmployees();
        } catch (error) {
            showNotification('Error updating employee', 'error');
        }
    }
}

async function deleteEmployee(employeeId) {
    if (confirm('Are you sure you want to delete this employee?')) {
        try {
            await authService.deleteEmployee(employeeId);
            showNotification('Employee deleted successfully', 'success');
            await loadEmployees();
        } catch (error) {
            showNotification('Error deleting employee', 'error');
        }
    }
}

// Dashboard initialization
function initializeDashboard() {
    loadSubscriptionStatus();
    loadQuestionsData();
}

async function loadSubscriptionStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/subscription/status`, {
            headers: authService.getAuthHeaders()
        });
        
        if (response.ok) {
            const status = await response.json();
            displaySubscriptionStatus(status);
        }
    } catch (error) {
        console.error('Error loading subscription status:', error);
    }
}

function displaySubscriptionStatus(status) {
    const subscriptionSection = document.getElementById('subscriptionSection');
    if (!subscriptionSection) return;

    subscriptionSection.innerHTML = `
        <div class="subscription-card ${status.is_trial ? 'trial' : status.plan}">
            <h3>${status.is_trial ? 'Trial' : status.plan} Plan</h3>
            <div class="subscription-details">
                <p><strong>Status:</strong> ${status.is_active ? 'Active' : 'Inactive'}</p>
                <p><strong>Questions Used:</strong> ${status.questions_used}/${status.questions_allowed}</p>
                ${status.end_date ? `<p><strong>Valid Until:</strong> ${new Date(status.end_date).toLocaleDateString()}</p>` : ''}
            </div>
        </div>
    `;
}

async function loadQuestionsData() {
    try {
        const response = await fetch(`${API_BASE_URL}/questions`, {
            headers: authService.getAuthHeaders()
        });
        
        if (response.ok) {
            const questionsData = await response.json();
            document.getElementById('totalQuestions').textContent = questionsData.length || 0;
        }
    } catch (error) {
        console.error('Error loading questions data:', error);
    }
}

// Helper function to show form errors
function showFormError(formId, message) {
    const existingError = document.querySelector(`#${formId} .form-error`);
    if (existingError) {
        existingError.remove();
    }

    const errorElement = document.createElement('div');
    errorElement.className = 'form-error alert alert-danger';
    errorElement.textContent = message;

    const form = document.getElementById(formId);
    if (form) {
        form.insertBefore(errorElement, form.firstChild);
    }

    setTimeout(() => {
        if (errorElement.parentNode) {
            errorElement.remove();
        }
    }, 5000);
}

// Notification system
function showNotification(message, type = 'info') {
    // Remove existing notifications
    document.querySelectorAll('.notification').forEach(notification => {
        notification.remove();
    });

    const notification = document.createElement('div');
    notification.className = `notification alert alert-${type === 'error' ? 'danger' : type}`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 10000;
        min-width: 300px;
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

// Make sure CSS classes are available
const style = document.createElement('style');
style.textContent = `
    .notification {
        animation: slideIn 0.3s ease-out;
    }
    
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    .form-step {
        display: none;
    }
    
    .form-step.active {
        display: block;
    }
`;
document.head.appendChild(style);