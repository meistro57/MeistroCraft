/**
 * Project Manager Component
 * Handles project lifecycle management including deletion, archiving, and Git integration
 */

class ProjectManager {
    constructor(ide) {
        this.ide = ide;
        this.projects = [];
        this.selectedProjects = new Set();
        this.currentFilter = 'all';
        this.searchQuery = '';
        this.selectedProject = null;
        this.contextMenu = null;
        
        this.init();
    }
    
    init() {
        this.createManagerHTML();
        this.setupEventListeners();
        this.loadProjects();
    }
    
    createManagerHTML() {
        const managerHTML = `
            <div id="projectManager" class="project-manager-overlay">
                <div class="project-manager-container">
                    <div class="project-manager-header">
                        <h2 class="project-manager-title">📁 Project Manager</h2>
                        <button class="project-manager-close" onclick="projectManager.close()">&times;</button>
                    </div>
                    
                    <div class="project-manager-toolbar">
                        <div class="project-search">
                            <input type="text" id="projectSearchInput" placeholder="Search projects..." />
                            <button class="project-btn project-btn-secondary" onclick="projectManager.refreshProjects()">
                                🔄 Refresh
                            </button>
                        </div>
                        
                        <div class="project-filter">
                            <select id="projectFilterSelect">
                                <option value="all">All Projects</option>
                                <option value="active">Active</option>
                                <option value="archived">Archived</option>
                                <option value="deleted">Deleted</option>
                            </select>
                            
                            <select id="projectSortSelect">
                                <option value="modified">Last Modified</option>
                                <option value="created">Date Created</option>
                                <option value="name">Name</option>
                                <option value="size">Size</option>
                            </select>
                        </div>
                        
                        <div class="project-actions">
                            <button class="project-btn project-btn-primary" onclick="projectManager.createNewProject()">
                                ➕ New Project
                            </button>
                            <button class="project-btn project-btn-secondary" onclick="projectManager.importProject()">
                                📥 Import
                            </button>
                        </div>
                    </div>
                    
                    <div class="project-manager-content">
                        <div class="project-list-container">
                            <div class="project-grid" id="projectGrid">
                                <!-- Projects will be populated here -->
                            </div>
                            
                            <div class="empty-state" id="emptyState" style="display: none;">
                                <div class="empty-state-icon">📂</div>
                                <div class="empty-state-title">No Projects Found</div>
                                <div class="empty-state-description">
                                    Create your first project to get started with development.
                                </div>
                                <button class="project-btn project-btn-primary" onclick="projectManager.createNewProject()">
                                    🚀 Create Project
                                </button>
                            </div>
                        </div>
                        
                        <div class="project-details-panel" id="projectDetailsPanel">
                            <div class="project-details-header">
                                <h3 class="project-details-title" id="projectDetailsTitle">Project Details</h3>
                                <button class="project-details-close" onclick="projectManager.closeDetails()">&times;</button>
                            </div>
                            
                            <div id="projectDetailsContent">
                                <!-- Project details will be populated here -->
                            </div>
                        </div>
                    </div>
                    
                    <div class="bulk-actions" id="bulkActions">
                        <div class="bulk-actions-info">
                            <span id="selectedCount">0</span> project(s) selected
                        </div>
                        <div class="bulk-actions-buttons">
                            <button class="project-btn project-btn-secondary" onclick="projectManager.bulkArchive()">
                                📦 Archive
                            </button>
                            <button class="project-btn project-btn-warning" onclick="projectManager.bulkRestore()">
                                🔄 Restore
                            </button>
                            <button class="project-btn project-btn-danger" onclick="projectManager.bulkDelete()">
                                🗑️ Delete
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Context Menu -->
            <div id="projectContextMenu" class="context-menu">
                <button class="context-menu-item" onclick="projectManager.openProject()">
                    📂 Open Project
                </button>
                <button class="context-menu-item" onclick="projectManager.showProjectDetails()">
                    ℹ️ Project Details
                </button>
                <div class="context-menu-separator"></div>
                <button class="context-menu-item" onclick="projectManager.duplicateProject()">
                    📋 Duplicate
                </button>
                <button class="context-menu-item" onclick="projectManager.exportProject()">
                    📤 Export
                </button>
                <div class="context-menu-separator"></div>
                <button class="context-menu-item" onclick="projectManager.initializeGit()">
                    🔗 Initialize Git
                </button>
                <button class="context-menu-item" onclick="projectManager.pushToGit()">
                    ⬆️ Push to Repository
                </button>
                <div class="context-menu-separator"></div>
                <button class="context-menu-item" onclick="projectManager.archiveProject()">
                    📦 Archive
                </button>
                <button class="context-menu-item danger" onclick="projectManager.deleteProject()">
                    🗑️ Delete
                </button>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', managerHTML);
    }
    
    setupEventListeners() {
        // Search functionality
        document.getElementById('projectSearchInput').addEventListener('input', (e) => {
            this.searchQuery = e.target.value.toLowerCase();
            this.filterAndRenderProjects();
        });
        
        // Filter and sort
        document.getElementById('projectFilterSelect').addEventListener('change', (e) => {
            this.currentFilter = e.target.value;
            this.filterAndRenderProjects();
        });
        
        document.getElementById('projectSortSelect').addEventListener('change', () => {
            this.filterAndRenderProjects();
        });
        
        // Click outside to close context menu and details
        document.addEventListener('click', (e) => {
            if (this.contextMenu && !this.contextMenu.contains(e.target)) {
                this.hideContextMenu();
            }
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (document.getElementById('projectManager').classList.contains('show')) {
                if (e.key === 'Escape') {
                    this.close();
                } else if (e.key === 'Delete' && this.selectedProjects.size > 0) {
                    this.bulkDelete();
                } else if (e.ctrlKey && e.key === 'a') {
                    e.preventDefault();
                    this.selectAllProjects();
                }
            }
        });
    }
    
    async loadProjects() {
        try {
            this.showLoading();
            
            // Load projects from the API
            const response = await fetch('/api/projects');
            if (response.ok) {
                this.projects = await response.json();
            } else {
                // Fallback: scan project folders
                this.projects = await this.scanProjectFolders();
            }
            
            this.filterAndRenderProjects();
        } catch (error) {
            console.error('Failed to load projects:', error);
            this.projects = await this.scanProjectFolders();
            this.filterAndRenderProjects();
        } finally {
            this.hideLoading();
        }
    }
    
    async scanProjectFolders() {
        try {
            const response = await fetch('/api/files?path=projects');
            const data = await response.json();
            
            const projects = [];
            for (const item of data.items) {
                if (item.type === 'directory') {
                    const projectData = await this.analyzeProject(item.path);
                    projects.push(projectData);
                }
            }
            
            return projects;
        } catch (error) {
            console.error('Failed to scan project folders:', error);
            return [];
        }
    }
    
    async analyzeProject(projectPath) {
        try {
            // Try to read project metadata
            const metadataResponse = await fetch(`/api/files/content?path=${projectPath}/.meistrocraft/project.json`);
            let metadata = {};
            
            if (metadataResponse.ok) {
                const metadataFile = await metadataResponse.json();
                metadata = JSON.parse(metadataFile.content);
            }
            
            // Get project stats
            const stats = await this.getProjectStats(projectPath);
            
            return {
                id: this.generateProjectId(projectPath),
                name: metadata.name || this.extractProjectName(projectPath),
                description: metadata.description || 'No description available',
                path: projectPath,
                status: metadata.status || 'active',
                created: metadata.created || new Date().toISOString(),
                modified: metadata.modified || new Date().toISOString(),
                technologies: metadata.technologies || this.detectTechnologies(projectPath),
                type: metadata.type || 'unknown',
                git: metadata.git || { initialized: false },
                stats: stats,
                metadata: metadata
            };
        } catch (error) {
            console.error('Failed to analyze project:', error);
            return {
                id: this.generateProjectId(projectPath),
                name: this.extractProjectName(projectPath),
                description: 'Failed to load project details',
                path: projectPath,
                status: 'unknown',
                created: new Date().toISOString(),
                modified: new Date().toISOString(),
                technologies: [],
                type: 'unknown',
                git: { initialized: false },
                stats: { files: 0, size: 0 },
                metadata: {}
            };
        }
    }
    
    async getProjectStats(projectPath) {
        try {
            const response = await fetch(`/api/projects/${encodeURIComponent(projectPath)}/stats`);
            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.error('Failed to get project stats:', error);
        }
        
        return { files: 0, size: 0, commits: 0, branches: 0 };
    }
    
    async detectTechnologies(projectPath) {
        const technologies = [];
        
        try {
            // Check for common config files
            const configFiles = [
                'package.json', 'requirements.txt', 'Gemfile', 'composer.json',
                'pom.xml', 'build.gradle', 'Cargo.toml', 'go.mod'
            ];
            
            for (const file of configFiles) {
                try {
                    const response = await fetch(`/api/files/content?path=${projectPath}/${file}`);
                    if (response.ok) {
                        technologies.push(this.getTechFromConfigFile(file));
                    }
                } catch (e) {
                    // File doesn't exist, continue
                }
            }
        } catch (error) {
            console.error('Failed to detect technologies:', error);
        }
        
        return technologies.filter(Boolean);
    }
    
    getTechFromConfigFile(filename) {
        const techMap = {
            'package.json': 'Node.js',
            'requirements.txt': 'Python',
            'Gemfile': 'Ruby',
            'composer.json': 'PHP',
            'pom.xml': 'Java',
            'build.gradle': 'Java',
            'Cargo.toml': 'Rust',
            'go.mod': 'Go'
        };
        
        return techMap[filename];
    }
    
    generateProjectId(path) {
        return btoa(path).replace(/[^a-zA-Z0-9]/g, '');
    }
    
    extractProjectName(path) {
        return path.split('/').pop() || 'Unnamed Project';
    }
    
    filterAndRenderProjects() {
        let filteredProjects = this.projects;
        
        // Apply status filter
        if (this.currentFilter !== 'all') {
            filteredProjects = filteredProjects.filter(p => p.status === this.currentFilter);
        }
        
        // Apply search filter
        if (this.searchQuery) {
            filteredProjects = filteredProjects.filter(p => 
                p.name.toLowerCase().includes(this.searchQuery) ||
                p.description.toLowerCase().includes(this.searchQuery) ||
                p.technologies.some(tech => tech.toLowerCase().includes(this.searchQuery))
            );
        }
        
        // Apply sorting
        const sortBy = document.getElementById('projectSortSelect').value;
        filteredProjects.sort((a, b) => {
            switch (sortBy) {
                case 'name':
                    return a.name.localeCompare(b.name);
                case 'created':
                    return new Date(b.created) - new Date(a.created);
                case 'size':
                    return (b.stats.size || 0) - (a.stats.size || 0);
                case 'modified':
                default:
                    return new Date(b.modified) - new Date(a.modified);
            }
        });
        
        this.renderProjects(filteredProjects);
    }
    
    renderProjects(projects) {
        const grid = document.getElementById('projectGrid');
        const emptyState = document.getElementById('emptyState');
        
        if (projects.length === 0) {
            grid.style.display = 'none';
            emptyState.style.display = 'block';
            return;
        }
        
        grid.style.display = 'grid';
        emptyState.style.display = 'none';
        
        grid.innerHTML = projects.map(project => this.createProjectCard(project)).join('');
        
        // Add event listeners to project cards
        grid.querySelectorAll('.project-card').forEach(card => {
            const projectId = card.dataset.projectId;
            
            card.addEventListener('click', (e) => {
                if (e.ctrlKey || e.metaKey) {
                    this.toggleProjectSelection(projectId);
                } else {
                    this.selectProject(projectId);
                }
            });
            
            card.addEventListener('dblclick', () => {
                this.openProject(projectId);
            });
            
            card.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                this.showContextMenu(e, projectId);
            });
        });
        
        this.updateBulkActions();
    }
    
    createProjectCard(project) {
        const isSelected = this.selectedProjects.has(project.id);
        const statusClass = project.status || 'active';
        
        return `
            <div class="project-card ${isSelected ? 'selected' : ''}" data-project-id="${project.id}">
                <div class="project-card-header">
                    <h3 class="project-name">${this.escapeHtml(project.name)}</h3>
                    <span class="project-status ${statusClass}">${statusClass}</span>
                </div>
                
                <p class="project-description">${this.escapeHtml(project.description)}</p>
                
                <div class="project-meta">
                    ${project.technologies.map(tech => `<span class="project-tech-tag">${tech}</span>`).join('')}
                </div>
                
                <div class="project-info">
                    <span>Modified: ${this.formatDate(project.modified)}</span>
                    <span>${this.formatFileSize(project.stats.size || 0)}</span>
                </div>
                
                <div class="project-actions-card">
                    <button class="project-btn project-btn-primary" onclick="projectManager.openProject('${project.id}')">
                        📂 Open
                    </button>
                    <button class="project-btn project-btn-secondary" onclick="projectManager.showProjectDetails('${project.id}')">
                        ℹ️ Details
                    </button>
                    ${this.getProjectActionButtons(project)}
                </div>
            </div>
        `;
    }
    
    getProjectActionButtons(project) {
        const buttons = [];
        
        if (project.status === 'active') {
            buttons.push(`
                <button class="project-btn project-btn-warning" onclick="projectManager.archiveProject('${project.id}')">
                    📦
                </button>
            `);
        } else if (project.status === 'archived') {
            buttons.push(`
                <button class="project-btn project-btn-success" onclick="projectManager.restoreProject('${project.id}')">
                    🔄
                </button>
            `);
        }
        
        if (project.git?.initialized) {
            buttons.push(`
                <button class="project-btn project-btn-secondary" onclick="projectManager.pushToGit('${project.id}')">
                    ⬆️
                </button>
            `);
        } else {
            buttons.push(`
                <button class="project-btn project-btn-secondary" onclick="projectManager.initializeGit('${project.id}')">
                    🔗
                </button>
            `);
        }
        
        return buttons.join('');
    }
    
    selectProject(projectId) {
        this.selectedProjects.clear();
        this.selectedProjects.add(projectId);
        this.updateSelection();
    }
    
    toggleProjectSelection(projectId) {
        if (this.selectedProjects.has(projectId)) {
            this.selectedProjects.delete(projectId);
        } else {
            this.selectedProjects.add(projectId);
        }
        this.updateSelection();
    }
    
    selectAllProjects() {
        const visibleProjects = document.querySelectorAll('.project-card[data-project-id]');
        visibleProjects.forEach(card => {
            this.selectedProjects.add(card.dataset.projectId);
        });
        this.updateSelection();
    }
    
    updateSelection() {
        document.querySelectorAll('.project-card').forEach(card => {
            const isSelected = this.selectedProjects.has(card.dataset.projectId);
            card.classList.toggle('selected', isSelected);
        });
        
        this.updateBulkActions();
    }
    
    updateBulkActions() {
        const bulkActions = document.getElementById('bulkActions');
        const selectedCount = document.getElementById('selectedCount');
        
        selectedCount.textContent = this.selectedProjects.size;
        
        if (this.selectedProjects.size > 0) {
            bulkActions.classList.add('show');
        } else {
            bulkActions.classList.remove('show');
        }
    }
    
    showContextMenu(event, projectId) {
        this.contextMenu = document.getElementById('projectContextMenu');
        this.selectedProject = projectId;
        
        // Position the context menu
        this.contextMenu.style.left = event.pageX + 'px';
        this.contextMenu.style.top = event.pageY + 'px';
        this.contextMenu.classList.add('show');
        
        // Adjust position if it goes off screen
        const rect = this.contextMenu.getBoundingClientRect();
        if (rect.right > window.innerWidth) {
            this.contextMenu.style.left = (event.pageX - rect.width) + 'px';
        }
        if (rect.bottom > window.innerHeight) {
            this.contextMenu.style.top = (event.pageY - rect.height) + 'px';
        }
    }
    
    hideContextMenu() {
        if (this.contextMenu) {
            this.contextMenu.classList.remove('show');
            this.selectedProject = null;
        }
    }
    
    async showProjectDetails(projectId = this.selectedProject) {
        const project = this.projects.find(p => p.id === projectId);
        if (!project) return;
        
        const panel = document.getElementById('projectDetailsPanel');
        const title = document.getElementById('projectDetailsTitle');
        const content = document.getElementById('projectDetailsContent');
        
        title.textContent = project.name;
        content.innerHTML = this.createProjectDetailsHTML(project);
        
        panel.classList.add('show');
        
        // Load additional details
        this.loadProjectDetailsData(project);
    }
    
    createProjectDetailsHTML(project) {
        return `
            <div class="project-detail-section">
                <div class="project-detail-label">Description</div>
                <div class="project-detail-value">${this.escapeHtml(project.description)}</div>
            </div>
            
            <div class="project-detail-section">
                <div class="project-detail-label">Project Type</div>
                <div class="project-detail-value">${project.type}</div>
            </div>
            
            <div class="project-detail-section">
                <div class="project-detail-label">Technologies</div>
                <div class="project-detail-value">
                    ${project.technologies.map(tech => `<span class="project-tech-tag">${tech}</span>`).join(' ')}
                </div>
            </div>
            
            <div class="project-detail-section">
                <div class="project-detail-label">Location</div>
                <div class="project-detail-value">${project.path}</div>
            </div>
            
            <div class="project-detail-section">
                <div class="project-detail-label">Git Repository</div>
                <div class="project-git-info">
                    <div class="project-git-status">
                        <div class="git-status-indicator ${project.git?.initialized ? 'connected' : 'disconnected'}"></div>
                        <span>${project.git?.initialized ? 'Git Initialized' : 'No Git Repository'}</span>
                    </div>
                    ${project.git?.remote ? `
                        <div>Remote: ${project.git.remote}</div>
                        <div>Branch: ${project.git.branch || 'main'}</div>
                    ` : ''}
                </div>
            </div>
            
            <div class="project-detail-section">
                <div class="project-detail-label">Statistics</div>
                <div class="project-stats">
                    <div class="project-stat">
                        <div class="project-stat-value">${project.stats.files || 0}</div>
                        <div class="project-stat-label">Files</div>
                    </div>
                    <div class="project-stat">
                        <div class="project-stat-value">${this.formatFileSize(project.stats.size || 0)}</div>
                        <div class="project-stat-label">Size</div>
                    </div>
                    <div class="project-stat">
                        <div class="project-stat-value">${project.stats.commits || 0}</div>
                        <div class="project-stat-label">Commits</div>
                    </div>
                    <div class="project-stat">
                        <div class="project-stat-value">${project.stats.branches || 0}</div>
                        <div class="project-stat-label">Branches</div>
                    </div>
                </div>
            </div>
            
            <div class="project-detail-section">
                <div class="project-detail-label">Dates</div>
                <div class="project-detail-value">
                    <div>Created: ${this.formatDate(project.created)}</div>
                    <div>Modified: ${this.formatDate(project.modified)}</div>
                </div>
            </div>
            
            <div class="project-detail-section">
                <div class="project-detail-label">Actions</div>
                <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 12px;">
                    <button class="project-btn project-btn-primary" onclick="projectManager.openProject('${project.id}')">
                        📂 Open Project
                    </button>
                    <button class="project-btn project-btn-secondary" onclick="projectManager.exportProject('${project.id}')">
                        📤 Export Project
                    </button>
                    <button class="project-btn project-btn-secondary" onclick="projectManager.duplicateProject('${project.id}')">
                        📋 Duplicate Project
                    </button>
                    ${!project.git?.initialized ? `
                        <button class="project-btn project-btn-secondary" onclick="projectManager.initializeGit('${project.id}')">
                            🔗 Initialize Git
                        </button>
                    ` : `
                        <button class="project-btn project-btn-secondary" onclick="projectManager.pushToGit('${project.id}')">
                            ⬆️ Push to Repository
                        </button>
                    `}
                    ${project.status === 'active' ? `
                        <button class="project-btn project-btn-warning" onclick="projectManager.archiveProject('${project.id}')">
                            📦 Archive Project
                        </button>
                    ` : project.status === 'archived' ? `
                        <button class="project-btn project-btn-success" onclick="projectManager.restoreProject('${project.id}')">
                            🔄 Restore Project
                        </button>
                    ` : ''}
                    <button class="project-btn project-btn-danger" onclick="projectManager.deleteProject('${project.id}')">
                        🗑️ Delete Project
                    </button>
                </div>
            </div>
        `;
    }
    
    async loadProjectDetailsData(project) {
        // Load additional project data like recent commits, file counts, etc.
        try {
            const response = await fetch(`/api/projects/${encodeURIComponent(project.path)}/details`);
            if (response.ok) {
                const details = await response.json();
                // Update the details panel with fresh data
                this.updateProjectDetailsData(details);
            }
        } catch (error) {
            console.error('Failed to load project details:', error);
        }
    }
    
    closeDetails() {
        document.getElementById('projectDetailsPanel').classList.remove('show');
    }
    
    // Project Actions
    async openProject(projectId = this.selectedProject) {
        const project = this.projects.find(p => p.id === projectId);
        if (!project) return;
        
        try {
            // Switch to the project directory in the IDE
            if (this.ide && this.ide.loadFiles) {
                await this.ide.loadFiles(project.path);
            }
            
            // Close the project manager
            this.close();
            
            // Show success message
            this.showNotification('success', `Opened project: ${project.name}`);
        } catch (error) {
            console.error('Failed to open project:', error);
            this.showNotification('error', 'Failed to open project');
        }
    }
    
    async createNewProject() {
        this.close();
        
        // Trigger the project wizard
        if (window.showProjectWizard) {
            window.showProjectWizard();
        } else if (this.ide && this.ide.showProjectWizard) {
            this.ide.showProjectWizard();
        }
    }
    
    async duplicateProject(projectId = this.selectedProject) {
        const project = this.projects.find(p => p.id === projectId);
        if (!project) return;
        
        const newName = prompt(`Enter name for duplicate project:`, `${project.name} Copy`);
        if (!newName) return;
        
        try {
            this.showLoading();
            
            const response = await fetch('/api/projects/duplicate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_path: project.path,
                    new_name: newName
                })
            });
            
            if (response.ok) {
                this.showNotification('success', `Project duplicated: ${newName}`);
                await this.refreshProjects();
            } else {
                throw new Error('Failed to duplicate project');
            }
        } catch (error) {
            console.error('Failed to duplicate project:', error);
            this.showNotification('error', 'Failed to duplicate project');
        } finally {
            this.hideLoading();
        }
    }
    
    async archiveProject(projectId = this.selectedProject) {
        const project = this.projects.find(p => p.id === projectId);
        if (!project) return;
        
        if (!confirm(`Archive project "${project.name}"?`)) return;
        
        try {
            await this.updateProjectStatus(project.id, 'archived');
            this.showNotification('success', `Project archived: ${project.name}`);
        } catch (error) {
            console.error('Failed to archive project:', error);
            this.showNotification('error', 'Failed to archive project');
        }
    }
    
    async restoreProject(projectId = this.selectedProject) {
        const project = this.projects.find(p => p.id === projectId);
        if (!project) return;
        
        try {
            await this.updateProjectStatus(project.id, 'active');
            this.showNotification('success', `Project restored: ${project.name}`);
        } catch (error) {
            console.error('Failed to restore project:', error);
            this.showNotification('error', 'Failed to restore project');
        }
    }
    
    async deleteProject(projectId = this.selectedProject) {
        const project = this.projects.find(p => p.id === projectId);
        if (!project) return;
        
        const confirmText = `DELETE ${project.name}`;
        const userInput = prompt(
            `⚠️ WARNING: This will permanently delete the project "${project.name}" and all its files.\n\n` +
            `Type "${confirmText}" to confirm deletion:`
        );
        
        if (userInput !== confirmText) return;
        
        try {
            this.showLoading();
            
            const response = await fetch(`/api/projects/${encodeURIComponent(project.path)}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                this.projects = this.projects.filter(p => p.id !== project.id);
                this.selectedProjects.delete(project.id);
                this.filterAndRenderProjects();
                this.showNotification('success', `Project deleted: ${project.name}`);
                this.closeDetails();
            } else {
                throw new Error('Failed to delete project');
            }
        } catch (error) {
            console.error('Failed to delete project:', error);
            this.showNotification('error', 'Failed to delete project');
        } finally {
            this.hideLoading();
        }
    }
    
    async exportProject(projectId = this.selectedProject) {
        const project = this.projects.find(p => p.id === projectId);
        if (!project) return;
        
        try {
            this.showLoading();
            
            const response = await fetch(`/api/projects/${encodeURIComponent(project.path)}/export`, {
                method: 'POST'
            });
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${project.name}.zip`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                this.showNotification('success', `Project exported: ${project.name}`);
            } else {
                throw new Error('Failed to export project');
            }
        } catch (error) {
            console.error('Failed to export project:', error);
            this.showNotification('error', 'Failed to export project');
        } finally {
            this.hideLoading();
        }
    }
    
    async importProject() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.zip';
        input.onchange = async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            
            try {
                this.showLoading();
                
                const formData = new FormData();
                formData.append('project_file', file);
                
                const response = await fetch('/api/projects/import', {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    this.showNotification('success', 'Project imported successfully');
                    await this.refreshProjects();
                } else {
                    throw new Error('Failed to import project');
                }
            } catch (error) {
                console.error('Failed to import project:', error);
                this.showNotification('error', 'Failed to import project');
            } finally {
                this.hideLoading();
            }
        };
        
        input.click();
    }
    
    async initializeGit(projectId = this.selectedProject) {
        const project = this.projects.find(p => p.id === projectId);
        if (!project) return;
        
        try {
            this.showLoading();
            
            const response = await fetch(`/api/projects/${encodeURIComponent(project.path)}/git/init`, {
                method: 'POST'
            });
            
            if (response.ok) {
                project.git.initialized = true;
                this.filterAndRenderProjects();
                this.showNotification('success', `Git initialized for: ${project.name}`);
                
                // Update details panel if open
                if (document.getElementById('projectDetailsPanel').classList.contains('show')) {
                    this.showProjectDetails(project.id);
                }
            } else {
                throw new Error('Failed to initialize Git');
            }
        } catch (error) {
            console.error('Failed to initialize Git:', error);
            this.showNotification('error', 'Failed to initialize Git');
        } finally {
            this.hideLoading();
        }
    }
    
    async pushToGit(projectId = this.selectedProject) {
        const project = this.projects.find(p => p.id === projectId);
        if (!project) return;
        
        if (!project.git?.initialized) {
            this.showNotification('error', 'Git not initialized for this project');
            return;
        }
        
        const remoteUrl = prompt('Enter Git remote URL:', project.git.remote || '');
        if (!remoteUrl) return;
        
        try {
            this.showLoading();
            
            const response = await fetch(`/api/projects/${encodeURIComponent(project.path)}/git/push`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    remote_url: remoteUrl,
                    branch: 'main'
                })
            });
            
            if (response.ok) {
                project.git.remote = remoteUrl;
                this.showNotification('success', `Pushed to repository: ${project.name}`);
            } else {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to push to repository');
            }
        } catch (error) {
            console.error('Failed to push to Git:', error);
            this.showNotification('error', `Failed to push: ${error.message}`);
        } finally {
            this.hideLoading();
        }
    }
    
    // Bulk Actions
    async bulkArchive() {
        if (this.selectedProjects.size === 0) return;
        
        if (!confirm(`Archive ${this.selectedProjects.size} project(s)?`)) return;
        
        try {
            this.showLoading();
            
            for (const projectId of this.selectedProjects) {
                await this.updateProjectStatus(projectId, 'archived');
            }
            
            this.selectedProjects.clear();
            this.updateSelection();
            this.showNotification('success', 'Projects archived successfully');
        } catch (error) {
            console.error('Failed to archive projects:', error);
            this.showNotification('error', 'Failed to archive some projects');
        } finally {
            this.hideLoading();
        }
    }
    
    async bulkRestore() {
        if (this.selectedProjects.size === 0) return;
        
        try {
            this.showLoading();
            
            for (const projectId of this.selectedProjects) {
                await this.updateProjectStatus(projectId, 'active');
            }
            
            this.selectedProjects.clear();
            this.updateSelection();
            this.showNotification('success', 'Projects restored successfully');
        } catch (error) {
            console.error('Failed to restore projects:', error);
            this.showNotification('error', 'Failed to restore some projects');
        } finally {
            this.hideLoading();
        }
    }
    
    async bulkDelete() {
        if (this.selectedProjects.size === 0) return;
        
        if (!confirm(`⚠️ Permanently delete ${this.selectedProjects.size} project(s)? This cannot be undone.`)) return;
        
        try {
            this.showLoading();
            
            for (const projectId of this.selectedProjects) {
                const project = this.projects.find(p => p.id === projectId);
                if (project) {
                    const response = await fetch(`/api/projects/${encodeURIComponent(project.path)}`, {
                        method: 'DELETE'
                    });
                    
                    if (response.ok) {
                        this.projects = this.projects.filter(p => p.id !== projectId);
                    }
                }
            }
            
            this.selectedProjects.clear();
            this.filterAndRenderProjects();
            this.showNotification('success', 'Projects deleted successfully');
        } catch (error) {
            console.error('Failed to delete projects:', error);
            this.showNotification('error', 'Failed to delete some projects');
        } finally {
            this.hideLoading();
        }
    }
    
    // Helper Methods
    async updateProjectStatus(projectId, status) {
        const project = this.projects.find(p => p.id === projectId);
        if (!project) return;
        
        try {
            const response = await fetch(`/api/projects/${encodeURIComponent(project.path)}/status`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status })
            });
            
            if (response.ok) {
                project.status = status;
                project.modified = new Date().toISOString();
                this.filterAndRenderProjects();
            } else {
                throw new Error('Failed to update project status');
            }
        } catch (error) {
            console.error('Failed to update project status:', error);
            throw error;
        }
    }
    
    async refreshProjects() {
        await this.loadProjects();
    }
    
    show() {
        document.getElementById('projectManager').classList.add('show');
        this.loadProjects();
    }
    
    close() {
        document.getElementById('projectManager').classList.remove('show');
        this.selectedProjects.clear();
        this.hideContextMenu();
        this.closeDetails();
    }
    
    showLoading() {
        const container = document.querySelector('.project-manager-container');
        if (!container.querySelector('.loading-overlay')) {
            const overlay = document.createElement('div');
            overlay.className = 'loading-overlay';
            overlay.innerHTML = '<div class="loading-spinner-large"></div>';
            container.appendChild(overlay);
        }
    }
    
    hideLoading() {
        const overlay = document.querySelector('.loading-overlay');
        if (overlay) {
            overlay.remove();
        }
    }
    
    showNotification(type, message) {
        // Use the IDE's notification system if available
        if (this.ide && this.ide.showNotification) {
            this.ide.showNotification(type, message);
        } else {
            // Fallback notification
            console.log(`${type.toUpperCase()}: ${message}`);
            alert(message);
        }
    }
    
    // Utility Methods
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    formatDate(dateString) {
        return new Date(dateString).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }
}

// Global instance
let projectManager = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Will be initialized by the main IDE when needed
});