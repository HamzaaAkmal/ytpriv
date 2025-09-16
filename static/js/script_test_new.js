// Simple test to check if button click works
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded - initializing YouTube scraper');

    const searchBtn = document.getElementById('searchBtn');
    const searchInput = document.getElementById('searchInput');
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');
    const errorDiv = document.getElementById('error');
    const errorText = document.getElementById('errorText');

    console.log('Elements found:', {
        searchBtn: !!searchBtn,
        searchInput: !!searchInput,
        loading: !!loading,
        results: !!results,
        errorDiv: !!errorDiv,
        errorText: !!errorText
    });

    if (searchBtn) {
        searchBtn.addEventListener('click', function() {
            console.log('Search button clicked');
            performSearch();
        });
    } else {
        console.error('Search button not found!');
    }

    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                console.log('Enter pressed in search input');
                performSearch();
            }
        });
    }

    async function performSearch() {
        console.log('performSearch called');

        const query = searchInput ? searchInput.value.trim() : '';

        console.log('Search params:', { query });

        if (!query) {
            showError('Please enter a search query!');
            return;
        }

        // Show loading with progress
        showLoading('🔍 Searching YouTube and Reddit...');
        hideResults();
        hideError();

        // Disable search button
        if (searchBtn) {
            searchBtn.disabled = true;
            searchBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Searching...';
        }

        try {
            console.log('Sending request to /search');

            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 180000); // 3 minute timeout for large data

            const response = await fetch('/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: query
                }),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            console.log('Response status:', response.status);
            console.log('Response headers:', response.headers);

            if (response.status === 200) {
                showLoading('📊 Processing comments from YouTube & Reddit...');
            }

            const data = await response.json();
            console.log('Response data received:', data);

            if (!response.ok) {
                throw new Error(data.error || `HTTP ${response.status}: ${response.statusText}`);
            }

            showLoading('💾 Saving unified data...');

            // Small delay to show the saving step
            setTimeout(() => {
                console.log('Calling displayResults with data:', data);
                displayResults(data);
            }, 1000);

        } catch (error) {
            console.error('Error in performSearch:', error);
            hideLoading();

            if (error.name === 'AbortError') {
                showError('Request timed out. The search is taking too long. Please try again.');
            } else {
                showError(`Search failed: ${error.message}`);
            }
        } finally {
            // Re-enable search button
            if (searchBtn) {
                searchBtn.disabled = false;
                searchBtn.innerHTML = '<i class="fas fa-search"></i> Search YouTube & Reddit';
            }
        }
    }

    function showLoading(message = 'Searching YouTube...') {
        if (loading) {
            loading.style.display = 'block';
            const loadingText = loading.querySelector('p');
            if (loadingText) {
                loadingText.textContent = message;
            }
        }
    }

    function hideLoading() {
        if (loading) loading.style.display = 'none';
    }

    function showResults() {
        if (results) results.style.display = 'block';
    }

    function hideResults() {
        if (results) results.style.display = 'none';
        hideSuccess();
    }

    function hideError() {
        if (errorDiv) errorDiv.style.display = 'none';
    }

    function showSuccessMessage(message) {
        // Create or update success message
        let successDiv = document.getElementById('success');
        if (!successDiv) {
            successDiv = document.createElement('div');
            successDiv.id = 'success';
            successDiv.className = 'success-message';
            successDiv.style.cssText = `
                background: linear-gradient(135deg, #4CAF50, #45a049);
                border: 1px solid #4CAF50;
                border-radius: 15px;
                padding: 20px;
                text-align: center;
                margin: 20px 0;
                animation: slideIn 0.5s ease-out;
            `;

            // Insert after loading div
            const loadingDiv = document.getElementById('loading');
            if (loadingDiv && loadingDiv.parentNode) {
                loadingDiv.parentNode.insertBefore(successDiv, loadingDiv.nextSibling);
            }
        }

        successDiv.innerHTML = `
            <i class="fas fa-check-circle" style="font-size: 2rem; color: white; margin-bottom: 10px;"></i>
            <p style="color: white; font-weight: 500; margin: 0;">${message}</p>
        `;

        successDiv.style.display = 'block';

        // Auto-hide after 5 seconds
        setTimeout(() => {
            if (successDiv) {
                successDiv.style.display = 'none';
            }
        }, 5000);
    }

    function hideSuccess() {
        const successDiv = document.getElementById('success');
        if (successDiv) {
            successDiv.style.display = 'none';
        }
    }

    function displayResults(data) {
        console.log('Displaying results:', data);

        // Update summary stats
        const totalVideos = document.getElementById('totalVideos');
        const totalRedditPosts = document.getElementById('totalRedditPosts');
        const totalComments = document.getElementById('totalComments');
        const uniqueComments = document.getElementById('uniqueComments');
        const totalReplies = document.getElementById('totalReplies');
        const grandTotal = document.getElementById('grandTotal');
        const attemptsMade = document.getElementById('attemptsMade');
        const batchId = document.getElementById('batchId');

        if (totalVideos) totalVideos.textContent = data.total_youtube_videos || 0;
        if (totalRedditPosts) totalRedditPosts.textContent = data.total_reddit_posts || 0;
        if (totalComments) totalComments.textContent = data.total_comments || 0;
        if (uniqueComments) uniqueComments.textContent = data.unique_comments || 0;
        if (totalReplies) totalReplies.textContent = data.total_replies || 0;
        if (grandTotal) grandTotal.textContent = data.grand_total || 0;
        if (attemptsMade) attemptsMade.textContent = data.attempts_made || 0;
        if (batchId) batchId.textContent = data.batch_id || 'N/A';

        // Display videos and posts
        const videosContainer = document.getElementById('videosContainer');
        if (videosContainer) {
            videosContainer.innerHTML = '';

            if (data.videos && data.videos.length > 0) {
                data.videos.forEach((videoData, index) => {
                    const videoCard = createUnifiedCard(videoData, index);
                    videosContainer.appendChild(videoCard);
                });
            }
        }

        // Hide loading and show results
        hideLoading();
        showResults();

        // Show success message with file info
        if (data.saved_to) {
            const sources = data.sources ? data.sources.join(' & ') : 'YouTube & Reddit';
            const targetStatus = data.target_achieved ? '✅ Target achieved!' : '⚠️ Target not fully achieved';
            const attemptsInfo = data.attempts_made ? ` (${data.attempts_made} attempts)` : '';
            showSuccessMessage(`${targetStatus} Data from ${sources} saved to: ${data.saved_to}${attemptsInfo}`);
        }

        // Scroll to results
        setTimeout(() => {
            if (results) {
                results.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }, 500);
    }

    function createUnifiedCard(videoData, index) {
        const card = document.createElement('div');
        card.className = 'video-batch-card';
        card.style.animationDelay = `${index * 0.1}s`;

        const source = videoData.source || 'unknown';
        const comments = videoData.comments || [];

        if (source === 'youtube') {
            const video = videoData.video_info || {};

            card.innerHTML = `
                <div class="video-header">
                    <img src="${video.thumbnail || ''}" alt="${video.title || 'Video'}" class="video-thumbnail-batch">
                    <div class="video-header-content">
                        <h4>${video.title || 'Untitled Video'}</h4>
                        <p class="video-channel">by ${video.channel || 'Unknown Channel'} • <span class="source-badge youtube-badge">YouTube</span></p>
                        <div class="video-stats">
                            <span><i class="fas fa-eye"></i> ${video.view_count || 0} views</span>
                            <span><i class="fas fa-comment"></i> ${comments.length} comments fetched</span>
                        </div>
                    </div>
                </div>
                <div class="comments-section">
                    <h5>Comments Preview (${Math.min(comments.length, 3)} of ${comments.length})</h5>
                    <div class="comments-list">
                        ${comments.slice(0, 3).map(comment => `
                            <div class="comment-item">
                                <div class="comment-author">${comment.author || 'Anonymous'}</div>
                                <div class="comment-text">${comment.text || ''}</div>
                                <div class="comment-meta">
                                    <span><i class="fas fa-thumbs-up"></i> ${comment.likes || 0}</span>
                                    <span><i class="fas fa-reply"></i> ${comment.reply_count || comment.replies?.length || 0} replies</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        } else if (source === 'reddit') {
            const post = videoData.post_info || {};

            card.innerHTML = `
                <div class="video-header reddit-header">
                    <div class="reddit-icon">
                        <i class="fab fa-reddit"></i>
                    </div>
                    <div class="video-header-content">
                        <h4>${post.title || 'Reddit Post'}</h4>
                        <p class="video-channel">r/${post.subreddit || 'unknown'} • <span class="source-badge reddit-badge">Reddit</span></p>
                        <div class="video-stats">
                            <span><i class="fas fa-comment"></i> ${comments.length} comments fetched</span>
                        </div>
                    </div>
                </div>
                <div class="comments-section">
                    <h5>Comments Preview (${Math.min(comments.length, 3)} of ${comments.length})</h5>
                    <div class="comments-list">
                        ${comments.slice(0, 3).map(comment => `
                            <div class="comment-item">
                                <div class="comment-author">u/${comment.author || 'Anonymous'}</div>
                                <div class="comment-text">${comment.text || ''}</div>
                                <div class="comment-meta">
                                    <span><i class="fas fa-thumbs-up"></i> ${comment.likes || 0}</span>
                                    <span><i class="fas fa-reply"></i> ${comment.replies?.length || 0} replies</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        return card;
    }
});
