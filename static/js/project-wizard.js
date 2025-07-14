/**
 * Project Wizard Component
 * Collects comprehensive project requirements and initiates AI-driven development
 */

class ProjectWizard {
    constructor(ide) {
        this.ide = ide;
        this.currentStep = 0;
        this.maxSteps = 6;
        this.projectData = {
            template: {},
            basic: {},
            technology: {},
            features: {},
            requirements: {},
            deployment: {}
        };
        
        this.init();
    }
    
    init() {
        this.createWizardHTML();
        this.setupEventListeners();
        this.populateFormOptions();
    }
    
    createWizardHTML() {
        const wizardHTML = `
            <div id="projectWizard" class="wizard-overlay">
                <div class="wizard-container">
                    <div class="wizard-header">
                        <h2 class="wizard-title">🚀 New Project Wizard</h2>
                        <button class="wizard-close" onclick="projectWizard.close()">&times;</button>
                    </div>
                    
                    <div class="wizard-progress">
                        <div class="progress-bar">
                            <div class="progress-fill" id="progressFill"></div>
                        </div>
                        <div class="progress-steps">
                            <span class="progress-step active">Template</span>
                            <span class="progress-step">Project Basics</span>
                            <span class="progress-step">Technology Stack</span>
                            <span class="progress-step">Features & Functionality</span>
                            <span class="progress-step">Requirements & Constraints</span>
                            <span class="progress-step">Review & Generate</span>
                        </div>
                    </div>
                    
                    <div class="wizard-content">
                        ${this.createStepHTML()}
                    </div>
                    
                    <div class="wizard-actions">
                        <button class="wizard-btn wizard-btn-secondary" id="prevBtn" onclick="projectWizard.previousStep()" disabled>Previous</button>
                        <button class="wizard-btn wizard-btn-primary" id="nextBtn" onclick="projectWizard.nextStep()">Next</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', wizardHTML);
    }
    
    createStepHTML() {
        return `
            <!-- Step 0: Template Selection -->
            <div class="wizard-step active" data-step="0">
                <h3 class="step-title">📋 Choose a Template</h3>
                <p class="step-description">Start with a pre-configured template or build from scratch.</p>
                
                <div class="form-group">
                    <label class="form-label">Project Templates</label>
                    <div class="feature-grid" id="templateOptions">
                        <div class="feature-card" data-template="blank">
                            <input type="radio" name="template" value="blank" style="display: none;" checked>
                            <div class="feature-icon">📝</div>
                            <div class="feature-title">Blank Project</div>
                            <div class="feature-description">Start from scratch with custom configuration</div>
                        </div>
                        <div class="feature-card" data-template="web-app-react">
                            <input type="radio" name="template" value="web-app-react" style="display: none;">
                            <div class="feature-icon">⚛️</div>
                            <div class="feature-title">React Web App</div>
                            <div class="feature-description">Modern React app with routing and styling</div>
                        </div>
                        <div class="feature-card" data-template="web-app-vue">
                            <input type="radio" name="template" value="web-app-vue" style="display: none;">
                            <div class="feature-icon">💚</div>
                            <div class="feature-title">Vue.js Web App</div>
                            <div class="feature-description">Vue 3 app with Composition API</div>
                        </div>
                        <div class="feature-card" data-template="api-fastapi">
                            <input type="radio" name="template" value="api-fastapi" style="display: none;">
                            <div class="feature-icon">⚡</div>
                            <div class="feature-title">FastAPI Backend</div>
                            <div class="feature-description">Python REST API with authentication</div>
                        </div>
                        <div class="feature-card" data-template="api-express">
                            <input type="radio" name="template" value="api-express" style="display: none;">
                            <div class="feature-icon">🚂</div>
                            <div class="feature-title">Express.js API</div>
                            <div class="feature-description">Node.js REST API with middleware</div>
                        </div>
                        <div class="feature-card" data-template="data-analysis">
                            <input type="radio" name="template" value="data-analysis" style="display: none;">
                            <div class="feature-icon">📊</div>
                            <div class="feature-title">Data Analysis</div>
                            <div class="feature-description">Jupyter notebooks with pandas and matplotlib</div>
                        </div>
                        <div class="feature-card" data-template="mobile-react-native">
                            <input type="radio" name="template" value="mobile-react-native" style="display: none;">
                            <div class="feature-icon">📱</div>
                            <div class="feature-title">React Native App</div>
                            <div class="feature-description">Cross-platform mobile application</div>
                        </div>
                        <div class="feature-card" data-template="fullstack-mern">
                            <input type="radio" name="template" value="fullstack-mern" style="display: none;">
                            <div class="feature-icon">🌟</div>
                            <div class="feature-title">MERN Stack</div>
                            <div class="feature-description">MongoDB, Express, React, Node.js</div>
                        </div>
                    </div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Template Benefits</label>
                    <div id="templateBenefits" class="template-benefits">
                        <p>Select a template above to see its included features and benefits.</p>
                    </div>
                </div>
            </div>
            
            <!-- Step 1: Project Basics -->
            <div class="wizard-step" data-step="1">
                <h3 class="step-title">📋 Project Basics</h3>
                <p class="step-description">Let's start with the fundamental details about your project.</p>
                
                <div class="form-group">
                    <label class="form-label">Project Name *</label>
                    <input type="text" class="form-input" id="projectName" placeholder="My Awesome Project" required>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Project Description *</label>
                    <textarea class="form-input form-textarea" id="projectDescription" placeholder="Describe what your project will do, its main purpose, and target users..." required></textarea>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Project Type *</label>
                    <select class="form-select" id="projectType" required>
                        <option value="">Select project type...</option>
                        <option value="web-app">Web Application</option>
                        <option value="mobile-app">Mobile Application</option>
                        <option value="desktop-app">Desktop Application</option>
                        <option value="api-service">API/Backend Service</option>
                        <option value="data-analysis">Data Analysis/ML</option>
                        <option value="automation-script">Automation/Script</option>
                        <option value="game">Game</option>
                        <option value="library-tool">Library/Tool</option>
                        <option value="other">Other</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Target Audience</label>
                    <input type="text" class="form-input" id="targetAudience" placeholder="e.g., Small businesses, Developers, General public">
                </div>
            </div>
            
            <!-- Step 2: Technology Stack -->
            <div class="wizard-step" data-step="2">
                <h3 class="step-title">⚙️ Technology Stack</h3>
                <p class="step-description">Choose the technologies and frameworks for your project.</p>
                
                <div class="form-group">
                    <label class="form-label">Primary Programming Language *</label>
                    <select class="form-select" id="primaryLanguage" required>
                        <option value="">Select language...</option>
                        <option value="javascript">JavaScript/TypeScript</option>
                        <option value="python">Python</option>
                        <option value="java">Java</option>
                        <option value="csharp">C#</option>
                        <option value="cpp">C++</option>
                        <option value="go">Go</option>
                        <option value="rust">Rust</option>
                        <option value="php">PHP</option>
                        <option value="ruby">Ruby</option>
                        <option value="swift">Swift</option>
                        <option value="kotlin">Kotlin</option>
                        <option value="other">Other</option>
                    </select>
                </div>
                
                <div class="form-group" id="frameworkGroup">
                    <label class="form-label">Framework/Library Preferences</label>
                    <div class="form-checkbox-group" id="frameworkOptions">
                        <!-- Dynamically populated based on language selection -->
                    </div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Database Type</label>
                    <select class="form-select" id="databaseType">
                        <option value="">No database needed</option>
                        <option value="sqlite">SQLite (lightweight)</option>
                        <option value="postgresql">PostgreSQL</option>
                        <option value="mysql">MySQL</option>
                        <option value="mongodb">MongoDB</option>
                        <option value="redis">Redis</option>
                        <option value="other">Other</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Additional Technologies</label>
                    <div class="form-checkbox-group">
                        <label class="form-checkbox">
                            <input type="checkbox" name="additionalTech" value="docker">
                            <span>🐳 Docker</span>
                        </label>
                        <label class="form-checkbox">
                            <input type="checkbox" name="additionalTech" value="testing">
                            <span>🧪 Testing Framework</span>
                        </label>
                        <label class="form-checkbox">
                            <input type="checkbox" name="additionalTech" value="ci-cd">
                            <span>🔄 CI/CD Pipeline</span>
                        </label>
                        <label class="form-checkbox">
                            <input type="checkbox" name="additionalTech" value="monitoring">
                            <span>📊 Monitoring/Logging</span>
                        </label>
                    </div>
                </div>
            </div>
            
            <!-- Step 3: Features & Functionality -->
            <div class="wizard-step" data-step="3">
                <h3 class="step-title">✨ Features & Functionality</h3>
                <p class="step-description">Select the core features and functionality your project needs.</p>
                
                <div class="form-group">
                    <label class="form-label">Core Features *</label>
                    <div class="feature-grid" id="coreFeatures">
                        <!-- Dynamically populated based on project type -->
                    </div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">User Authentication</label>
                    <select class="form-select" id="authType">
                        <option value="none">No authentication needed</option>
                        <option value="simple">Simple login/register</option>
                        <option value="oauth">OAuth (Google, GitHub, etc.)</option>
                        <option value="jwt">JWT tokens</option>
                        <option value="session">Session-based</option>
                        <option value="custom">Custom authentication</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label class="form-label">API Requirements</label>
                    <div class="form-checkbox-group">
                        <label class="form-checkbox">
                            <input type="checkbox" name="apiFeatures" value="rest-api">
                            <span>🌐 REST API</span>
                        </label>
                        <label class="form-checkbox">
                            <input type="checkbox" name="apiFeatures" value="graphql">
                            <span>📊 GraphQL</span>
                        </label>
                        <label class="form-checkbox">
                            <input type="checkbox" name="apiFeatures" value="websockets">
                            <span>⚡ WebSockets</span>
                        </label>
                        <label class="form-checkbox">
                            <input type="checkbox" name="apiFeatures" value="third-party">
                            <span>🔌 Third-party APIs</span>
                        </label>
                    </div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Additional Features</label>
                    <textarea class="form-input form-textarea" id="additionalFeatures" placeholder="Describe any specific features, integrations, or functionality not covered above..."></textarea>
                </div>
            </div>
            
            <!-- Step 4: Requirements & Constraints -->
            <div class="wizard-step" data-step="4">
                <h3 class="step-title">📐 Requirements & Constraints</h3>
                <p class="step-description">Specify technical requirements, constraints, and preferences.</p>
                
                <div class="form-group">
                    <label class="form-label">Performance Requirements</label>
                    <textarea class="form-input form-textarea" id="performanceReqs" placeholder="e.g., Handle 1000 concurrent users, Response time under 200ms, Process large datasets..."></textarea>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Security Requirements</label>
                    <div class="form-checkbox-group">
                        <label class="form-checkbox">
                            <input type="checkbox" name="securityFeatures" value="encryption">
                            <span>🔒 Data Encryption</span>
                        </label>
                        <label class="form-checkbox">
                            <input type="checkbox" name="securityFeatures" value="input-validation">
                            <span>🛡️ Input Validation</span>
                        </label>
                        <label class="form-checkbox">
                            <input type="checkbox" name="securityFeatures" value="rate-limiting">
                            <span>⏱️ Rate Limiting</span>
                        </label>
                        <label class="form-checkbox">
                            <input type="checkbox" name="securityFeatures" value="audit-logging">
                            <span>📝 Audit Logging</span>
                        </label>
                    </div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Deployment Environment</label>
                    <select class="form-select" id="deploymentEnv">
                        <option value="local">Local development only</option>
                        <option value="cloud-aws">AWS Cloud</option>
                        <option value="cloud-gcp">Google Cloud Platform</option>
                        <option value="cloud-azure">Microsoft Azure</option>
                        <option value="heroku">Heroku</option>
                        <option value="vercel">Vercel</option>
                        <option value="netlify">Netlify</option>
                        <option value="vps">VPS/Server</option>
                        <option value="other">Other</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Budget/Time Constraints</label>
                    <textarea class="form-input form-textarea" id="constraints" placeholder="Any budget limitations, timeline requirements, or technical constraints..."></textarea>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Special Requirements</label>
                    <textarea class="form-input form-textarea" id="specialReqs" placeholder="Accessibility requirements, compliance needs (GDPR, HIPAA), mobile responsiveness, etc..."></textarea>
                </div>
            </div>
            
            <!-- Step 5: Review & Generate -->
            <div class="wizard-step" data-step="5">
                <h3 class="step-title">🎯 Review & Generate</h3>
                <p class="step-description">Review your project specifications and generate the development plan.</p>
                
                <div class="project-summary" id="projectSummary">
                    <!-- Dynamically populated with project details -->
                </div>
                
                <div class="form-group">
                    <label class="form-label">Generation Options</label>
                    <div class="form-checkbox-group">
                        <label class="form-checkbox">
                            <input type="checkbox" id="generateStructure" checked>
                            <span>📁 Generate project structure</span>
                        </label>
                        <label class="form-checkbox">
                            <input type="checkbox" id="generateBoilerplate" checked>
                            <span>🏗️ Create boilerplate code</span>
                        </label>
                        <label class="form-checkbox">
                            <input type="checkbox" id="generateDocs" checked>
                            <span>📚 Generate documentation</span>
                        </label>
                        <label class="form-checkbox">
                            <input type="checkbox" id="generateTests">
                            <span>🧪 Create test templates</span>
                        </label>
                    </div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Additional Instructions</label>
                    <textarea class="form-input form-textarea" id="finalInstructions" placeholder="Any specific coding style, patterns, or additional instructions for the AI agents..."></textarea>
                </div>
            </div>
        `;
    }
    
    setupEventListeners() {
        // Language change listener to update framework options
        document.addEventListener('change', (e) => {
            if (e.target.id === 'primaryLanguage') {
                this.updateFrameworkOptions(e.target.value);
            }
            if (e.target.id === 'projectType') {
                this.updateCoreFeatures(e.target.value);
            }
        });
        
        // Checkbox styling
        document.addEventListener('change', (e) => {
            if (e.target.type === 'checkbox') {
                const label = e.target.closest('.form-checkbox');
                if (label) {
                    label.classList.toggle('selected', e.target.checked);
                }
            }
        });
        
        // Feature card clicks
        document.addEventListener('click', (e) => {
            if (e.target.closest('.feature-card')) {
                const card = e.target.closest('.feature-card');
                const checkbox = card.querySelector('input[type="checkbox"]');
                const radio = card.querySelector('input[type="radio"]');
                
                if (checkbox) {
                    checkbox.checked = !checkbox.checked;
                    card.classList.toggle('selected', checkbox.checked);
                } else if (radio) {
                    // Handle radio button selection for templates
                    const allCards = document.querySelectorAll('.feature-card[data-template]');
                    allCards.forEach(c => c.classList.remove('selected'));
                    radio.checked = true;
                    card.classList.add('selected');
                    this.updateTemplateBenefits(radio.value);
                }
            }
        });
    }
    
    populateFormOptions() {
        // Will be called when showing the wizard
    }
    
    updateTemplateBenefits(template) {
        const benefitsContainer = document.getElementById('templateBenefits');
        const templateBenefits = this.getTemplateBenefits(template);
        
        benefitsContainer.innerHTML = `
            <h4 style="color: #fff; margin-bottom: 12px;">${templateBenefits.title}</h4>
            <p style="color: #ccc; margin-bottom: 12px;">${templateBenefits.description}</p>
            <h5 style="color: #fff; margin-bottom: 8px;">Included Features:</h5>
            <ul>
                ${templateBenefits.features.map(feature => `<li>${feature}</li>`).join('')}
            </ul>
            <h5 style="color: #fff; margin: 12px 0 8px;">Technologies:</h5>
            <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                ${templateBenefits.technologies.map(tech => `<span class="tech-tag">${tech}</span>`).join('')}
            </div>
        `;
    }
    
    getTemplateBenefits(template) {
        const benefits = {
            'blank': {
                title: 'Blank Project',
                description: 'Start completely from scratch with full customization control.',
                features: ['Complete flexibility', 'Custom architecture', 'No preset limitations'],
                technologies: ['Custom choice']
            },
            'web-app-react': {
                title: 'React Web Application',
                description: 'Modern React application with best practices and common features.',
                features: ['Component-based architecture', 'React Router for navigation', 'State management setup', 'CSS-in-JS styling', 'Development server', 'Build optimization'],
                technologies: ['React 18', 'React Router', 'Styled Components', 'Webpack', 'ESLint']
            },
            'web-app-vue': {
                title: 'Vue.js Web Application',
                description: 'Vue 3 application with Composition API and modern tooling.',
                features: ['Composition API setup', 'Vue Router', 'Vuex/Pinia state management', 'Component library', 'TypeScript support', 'Hot reload'],
                technologies: ['Vue 3', 'Vue Router', 'Pinia', 'Vite', 'TypeScript']
            },
            'api-fastapi': {
                title: 'FastAPI Backend',
                description: 'High-performance Python API with automatic documentation.',
                features: ['REST API endpoints', 'Automatic OpenAPI docs', 'Data validation', 'Authentication middleware', 'Database integration', 'Testing setup'],
                technologies: ['FastAPI', 'Pydantic', 'SQLAlchemy', 'pytest', 'Uvicorn']
            },
            'api-express': {
                title: 'Express.js API',
                description: 'Node.js REST API with middleware and best practices.',
                features: ['RESTful routing', 'Middleware setup', 'Error handling', 'Logging', 'CORS configuration', 'Security headers'],
                technologies: ['Express.js', 'Morgan', 'Helmet', 'CORS', 'dotenv']
            },
            'data-analysis': {
                title: 'Data Analysis Project',
                description: 'Jupyter notebook environment with data science libraries.',
                features: ['Jupyter notebooks', 'Data visualization', 'Statistical analysis', 'ML model templates', 'Data cleaning utilities'],
                technologies: ['Jupyter', 'pandas', 'matplotlib', 'scikit-learn', 'NumPy']
            },
            'mobile-react-native': {
                title: 'React Native Mobile App',
                description: 'Cross-platform mobile application for iOS and Android.',
                features: ['Cross-platform code', 'Native navigation', 'Component library', 'State management', 'Platform-specific styling'],
                technologies: ['React Native', 'React Navigation', 'Redux Toolkit', 'Expo']
            },
            'fullstack-mern': {
                title: 'MERN Stack Application',
                description: 'Full-stack web application with MongoDB, Express, React, and Node.js.',
                features: ['Frontend and backend', 'Database integration', 'User authentication', 'API development', 'Deployment ready'],
                technologies: ['MongoDB', 'Express.js', 'React', 'Node.js', 'JWT']
            }
        };
        
        return benefits[template] || benefits['blank'];
    }
    
    updateFrameworkOptions(language) {
        const frameworkContainer = document.getElementById('frameworkOptions');
        const frameworks = this.getFrameworksForLanguage(language);
        
        frameworkContainer.innerHTML = frameworks.map(fw => `
            <label class="form-checkbox">
                <input type="checkbox" name="frameworks" value="${fw.value}">
                <span>${fw.icon} ${fw.name}</span>
            </label>
        `).join('');
    }
    
    updateCoreFeatures(projectType) {
        const featuresContainer = document.getElementById('coreFeatures');
        const features = this.getFeaturesForProjectType(projectType);
        
        featuresContainer.innerHTML = features.map(feature => `
            <div class="feature-card" data-feature="${feature.value}">
                <input type="checkbox" name="coreFeatures" value="${feature.value}" style="display: none;">
                <div class="feature-icon">${feature.icon}</div>
                <div class="feature-title">${feature.name}</div>
                <div class="feature-description">${feature.description}</div>
            </div>
        `).join('');
    }
    
    getFrameworksForLanguage(language) {
        const frameworkMap = {
            javascript: [
                { value: 'react', name: 'React', icon: '⚛️' },
                { value: 'vue', name: 'Vue.js', icon: '💚' },
                { value: 'angular', name: 'Angular', icon: '🅰️' },
                { value: 'express', name: 'Express.js', icon: '🚂' },
                { value: 'nextjs', name: 'Next.js', icon: '▲' },
                { value: 'nuxt', name: 'Nuxt.js', icon: '💚' }
            ],
            python: [
                { value: 'django', name: 'Django', icon: '🎸' },
                { value: 'flask', name: 'Flask', icon: '🌶️' },
                { value: 'fastapi', name: 'FastAPI', icon: '⚡' },
                { value: 'streamlit', name: 'Streamlit', icon: '📊' },
                { value: 'pygame', name: 'Pygame', icon: '🎮' }
            ],
            java: [
                { value: 'spring', name: 'Spring Boot', icon: '🍃' },
                { value: 'android', name: 'Android SDK', icon: '🤖' }
            ],
            csharp: [
                { value: 'aspnet', name: 'ASP.NET Core', icon: '🔷' },
                { value: 'unity', name: 'Unity', icon: '🎮' }
            ]
        };
        
        return frameworkMap[language] || [];
    }
    
    getFeaturesForProjectType(projectType) {
        const featureMap = {
            'web-app': [
                { value: 'responsive-ui', name: 'Responsive UI', description: 'Mobile-friendly interface', icon: '📱' },
                { value: 'user-dashboard', name: 'User Dashboard', description: 'Personalized user interface', icon: '📊' },
                { value: 'admin-panel', name: 'Admin Panel', description: 'Administrative interface', icon: '⚙️' },
                { value: 'file-upload', name: 'File Upload', description: 'File handling capabilities', icon: '📁' }
            ],
            'api-service': [
                { value: 'crud-operations', name: 'CRUD Operations', description: 'Create, Read, Update, Delete', icon: '🔄' },
                { value: 'authentication', name: 'Authentication', description: 'User authentication system', icon: '🔐' },
                { value: 'rate-limiting', name: 'Rate Limiting', description: 'API usage controls', icon: '⏱️' },
                { value: 'documentation', name: 'API Documentation', description: 'Auto-generated docs', icon: '📚' }
            ],
            'mobile-app': [
                { value: 'native-features', name: 'Native Features', description: 'Camera, GPS, notifications', icon: '📱' },
                { value: 'offline-support', name: 'Offline Support', description: 'Works without internet', icon: '📡' },
                { value: 'push-notifications', name: 'Push Notifications', description: 'Real-time messaging', icon: '🔔' },
                { value: 'app-store', name: 'App Store Ready', description: 'Distribution preparation', icon: '🏪' }
            ]
        };
        
        return featureMap[projectType] || [
            { value: 'custom-feature', name: 'Custom Features', description: 'Project-specific functionality', icon: '⭐' }
        ];
    }
    
    show() {
        document.getElementById('projectWizard').classList.add('show');
        this.updateProgress();
        
        // Initialize template benefits for default selection
        setTimeout(() => {
            this.updateTemplateBenefits('blank');
            document.querySelector('[data-template="blank"]').classList.add('selected');
        }, 100);
    }
    
    close() {
        document.getElementById('projectWizard').classList.remove('show');
        // Reset wizard state
        this.currentStep = 0;
        this.projectData = { template: {}, basic: {}, technology: {}, features: {}, requirements: {}, deployment: {} };
        this.updateProgress();
        this.updateStepVisibility();
        this.updateButtons();
    }
    
    nextStep() {
        if (this.validateCurrentStep()) {
            this.saveCurrentStepData();
            
            if (this.currentStep < this.maxSteps - 1) {
                this.currentStep++;
                this.updateStepVisibility();
                this.updateProgress();
                this.updateButtons();
                
                if (this.currentStep === this.maxSteps - 1) {
                    this.generateProjectSummary();
                }
            } else {
                this.generateProject();
            }
        }
    }
    
    previousStep() {
        if (this.currentStep > 0) {
            this.currentStep--;
            this.updateStepVisibility();
            this.updateProgress();
            this.updateButtons();
        }
    }
    
    validateCurrentStep() {
        const currentStepElement = document.querySelector(`.wizard-step[data-step="${this.currentStep}"]`);
        const requiredFields = currentStepElement.querySelectorAll('[required]');
        
        for (let field of requiredFields) {
            if (!field.value.trim()) {
                field.focus();
                field.style.borderColor = '#ff4444';
                setTimeout(() => field.style.borderColor = '', 3000);
                return false;
            }
        }
        
        return true;
    }
    
    saveCurrentStepData() {
        const stepData = {};
        const currentStepElement = document.querySelector(`.wizard-step[data-step="${this.currentStep}"]`);
        const inputs = currentStepElement.querySelectorAll('input, select, textarea');
        
        inputs.forEach(input => {
            if (input.type === 'checkbox') {
                if (!stepData[input.name]) stepData[input.name] = [];
                if (input.checked) stepData[input.name].push(input.value);
            } else {
                stepData[input.id] = input.value;
            }
        });
        
        // Store in appropriate section
        const sections = ['template', 'basic', 'technology', 'features', 'requirements', 'deployment'];
        this.projectData[sections[this.currentStep]] = stepData;
    }
    
    updateStepVisibility() {
        document.querySelectorAll('.wizard-step').forEach((step, index) => {
            step.classList.toggle('active', index === this.currentStep);
        });
        
        document.querySelectorAll('.progress-step').forEach((step, index) => {
            step.classList.toggle('active', index === this.currentStep);
            step.classList.toggle('completed', index < this.currentStep);
        });
    }
    
    updateProgress() {
        const progress = ((this.currentStep + 1) / this.maxSteps) * 100;
        document.getElementById('progressFill').style.width = `${progress}%`;
    }
    
    updateButtons() {
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');
        
        prevBtn.disabled = this.currentStep === 0;
        
        if (this.currentStep === this.maxSteps - 1) {
            nextBtn.textContent = 'Generate Project';
            nextBtn.className = 'wizard-btn wizard-btn-success';
        } else {
            nextBtn.textContent = 'Next';
            nextBtn.className = 'wizard-btn wizard-btn-primary';
        }
    }
    
    generateProjectSummary() {
        const summary = document.getElementById('projectSummary');
        const { basic, technology, features, requirements } = this.projectData;
        
        summary.innerHTML = `
            <div class="summary-item">
                <span class="summary-label">Project Name:</span>
                <span class="summary-value">${basic.projectName || 'N/A'}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Type:</span>
                <span class="summary-value">${basic.projectType || 'N/A'}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Language:</span>
                <span class="summary-value">${technology.primaryLanguage || 'N/A'}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Frameworks:</span>
                <span class="summary-value">
                    ${(technology.frameworks || []).map(fw => `<span class="tech-tag">${fw}</span>`).join('')}
                </span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Database:</span>
                <span class="summary-value">${technology.databaseType || 'None'}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Core Features:</span>
                <span class="summary-value">
                    ${(features.coreFeatures || []).map(feature => `<span class="tech-tag">${feature}</span>`).join('')}
                </span>
            </div>
        `;
    }
    
    async generateProject() {
        const nextBtn = document.getElementById('nextBtn');
        const originalText = nextBtn.textContent;
        
        nextBtn.innerHTML = '<span class="loading-spinner"></span>Generating...';
        nextBtn.disabled = true;
        
        try {
            // Compile all project data
            const fullProjectSpec = this.compileProjectSpecification();
            
            // Send to AI for project generation
            await this.sendProjectToAI(fullProjectSpec);
            
            // Close wizard and show success message
            this.close();
            this.showSuccessMessage();
            
        } catch (error) {
            console.error('Project generation failed:', error);
            alert('Failed to generate project. Please try again.');
        } finally {
            nextBtn.innerHTML = originalText;
            nextBtn.disabled = false;
        }
    }
    
    compileProjectSpecification() {
        this.saveCurrentStepData(); // Save final step data
        
        const spec = {
            metadata: {
                timestamp: new Date().toISOString(),
                wizard_version: "1.0",
                template: this.projectData.template.template || 'blank'
            },
            project: {
                name: this.projectData.basic.projectName,
                description: this.projectData.basic.projectDescription,
                type: this.projectData.basic.projectType,
                target_audience: this.projectData.basic.targetAudience
            },
            technology: {
                primary_language: this.projectData.technology.primaryLanguage,
                frameworks: this.projectData.technology.frameworks || [],
                database: this.projectData.technology.databaseType,
                additional_tech: this.projectData.technology.additionalTech || []
            },
            features: {
                core_features: this.projectData.features.coreFeatures || [],
                authentication: this.projectData.features.authType,
                api_features: this.projectData.features.apiFeatures || [],
                additional_features: this.projectData.features.additionalFeatures
            },
            requirements: {
                performance: this.projectData.requirements.performanceReqs,
                security: this.projectData.requirements.securityFeatures || [],
                deployment: this.projectData.requirements.deploymentEnv,
                constraints: this.projectData.requirements.constraints,
                special: this.projectData.requirements.specialReqs
            },
            generation_options: {
                generate_structure: document.getElementById('generateStructure')?.checked || false,
                generate_boilerplate: document.getElementById('generateBoilerplate')?.checked || false,
                generate_docs: document.getElementById('generateDocs')?.checked || false,
                generate_tests: document.getElementById('generateTests')?.checked || false,
                final_instructions: this.projectData.deployment.finalInstructions
            }
        };
        
        return spec;
    }
    
    async sendProjectToAI(projectSpec) {
        try {
            const response = await fetch('/api/projects/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    project_spec: projectSpec,
                    session_id: this.ide ? this.ide.sessionId : null
                })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to generate project');
            }
            
            const result = await response.json();
            console.log('Project generation started:', result);
            
            // Refresh file explorer to show new project
            if (this.ide && this.ide.loadFiles) {
                setTimeout(() => this.ide.loadFiles(), 2000);
            }
            
            return result;
        } catch (error) {
            console.error('Project generation error:', error);
            throw error;
        }
    }
    
    createAIPrompt(spec) {
        return `🚀 **PROJECT GENERATION REQUEST**

I need you to create a complete ${spec.project.type} project based on the following specifications:

## Project Overview
- **Name**: ${spec.project.name}
- **Description**: ${spec.project.description}
- **Target Audience**: ${spec.project.target_audience}

## Technology Stack
- **Primary Language**: ${spec.technology.primary_language}
- **Frameworks**: ${spec.technology.frameworks.join(', ') || 'None specified'}
- **Database**: ${spec.technology.database || 'None'}
- **Additional Technologies**: ${spec.technology.additional_tech.join(', ') || 'None'}

## Core Features
${spec.features.core_features.map(feature => `- ${feature}`).join('\n') || '- Basic functionality'}

## Authentication & API
- **Authentication Type**: ${spec.features.authentication || 'None'}
- **API Features**: ${spec.features.api_features.join(', ') || 'None'}

## Requirements & Constraints
- **Performance**: ${spec.requirements.performance || 'Standard performance'}
- **Security**: ${spec.requirements.security.join(', ') || 'Basic security'}
- **Deployment**: ${spec.requirements.deployment || 'Local development'}
- **Constraints**: ${spec.requirements.constraints || 'None specified'}

## Generation Instructions
${spec.generation_options.generate_structure ? '✅ Generate complete project structure\n' : ''}${spec.generation_options.generate_boilerplate ? '✅ Create boilerplate code\n' : ''}${spec.generation_options.generate_docs ? '✅ Generate documentation\n' : ''}${spec.generation_options.generate_tests ? '✅ Create test templates\n' : ''}

## Additional Instructions
${spec.generation_options.final_instructions || 'Follow best practices and create a production-ready foundation.'}

Please create a complete, functional project that meets these specifications. Start with the project structure, then implement core functionality, and provide clear documentation for next steps.`;
    }
    
    showSuccessMessage() {
        // Show a success notification or message
        if (this.ide && this.ide.addMessage) {
            this.ide.addMessage('success', '🎉 Project generation started! The AI is now creating your project structure and code.');
        }
    }
}

// Expose to global window object
window.ProjectWizard = ProjectWizard;

// Global instance
let projectWizard = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Will be initialized by the main IDE when needed
});