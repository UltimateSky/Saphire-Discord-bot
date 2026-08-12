document.addEventListener('DOMContentLoaded', () => {
    
    // Server Dropdown Toggle
    const serverDropdownBtn = document.getElementById('serverDropdownBtn');
    const serverDropdownMenu = document.getElementById('serverDropdownMenu');
    
    if (serverDropdownBtn && serverDropdownMenu) {
        serverDropdownBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            serverDropdownMenu.classList.toggle('active');
        });
        
        // Close when clicking outside
        document.addEventListener('click', (e) => {
            if (!serverDropdownBtn.contains(e.target) && !serverDropdownMenu.contains(e.target)) {
                serverDropdownMenu.classList.remove('active');
            }
        });
    }
    // Floating Save Bar Logic
    const configForm = document.getElementById('configForm');
    const floatingSave = document.getElementById('floatingSave');
    const resetBtn = document.getElementById('resetBtn');
    
    let originalData = {};
    
    if (configForm) {
        // Store original values
        const inputs = configForm.querySelectorAll('select, input, textarea');
        inputs.forEach(input => {
            if (input.type === 'checkbox') {
                originalData[input.id] = input.checked;
            } else {
                originalData[input.id] = input.value;
            }
            
            // Add change listener to show floating bar
            input.addEventListener('change', () => {
                floatingSave.classList.add('show');
            });
        });
        
        // Reset Button
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                inputs.forEach(input => {
                    if (input.type === 'checkbox') {
                        input.checked = originalData[input.id];
                    } else {
                        input.value = originalData[input.id];
                    }
                });
                floatingSave.classList.remove('show');
            });
        }
        
        // Save Config
        configForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const guildId = document.getElementById('config_guild_id').value;
            
            const logChannelId = document.getElementById('log_channel_id').value;
            const ticketCategoryId = document.getElementById('ticket_category_id').value;
            const autoRoleId = document.getElementById('auto_role_id').value;
            
            const automodEnabled = document.getElementById('automod_enabled')?.checked ? 1 : 0;
            const levelingEnabled = document.getElementById('leveling_enabled')?.checked ? 1 : 0;
            const ticketsEnabled = document.getElementById('tickets_enabled')?.checked ? 1 : 0;
            
            // New Fields
            const botEnabled = document.getElementById('bot_enabled')?.checked ? 1 : 0;
            const welcomeEnabled = document.getElementById('welcome_enabled')?.checked ? 1 : 0;
            const welcomeChannelId = document.getElementById('welcome_channel_id')?.value;
            const welcomeMessage = document.getElementById('welcome_message')?.value;
            const welcomeBgUrl = document.getElementById('welcome_bg_url')?.value;
            
            let slowmodeDelay = 0;
            if (document.getElementById('slowmode_delay')) {
                const val = parseInt(document.getElementById('slowmode_delay').value) || 0;
                const unit = parseInt(document.getElementById('slowmode_unit').value) || 1;
                slowmodeDelay = val * unit;
            }
            
            // Show saving state on button
            const submitBtn = configForm.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = 'Saving...';
            submitBtn.disabled = true;
            
            try {
                const response = await fetch('/api/save_config', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ 
                        guild_id: guildId, 
                        log_channel_id: logChannelId || null,
                        ticket_category_id: ticketCategoryId || null,
                        auto_role_id: autoRoleId || null,
                        automod_enabled: automodEnabled,
                        leveling_enabled: levelingEnabled,
                        tickets_enabled: ticketsEnabled,
                        bot_enabled: botEnabled,
                        slowmode_delay: slowmodeDelay,
                        welcome_enabled: welcomeEnabled,
                        welcome_channel_id: welcomeChannelId || null,
                        welcome_message: welcomeMessage || null,
                        welcome_bg_url: welcomeBgUrl || null
                    })
                });
                
                const result = await response.json();
                if (result.success) {
                    // Update original data
                    inputs.forEach(input => {
                        if (input.type === 'checkbox') {
                            originalData[input.id] = input.checked;
                        } else {
                            originalData[input.id] = input.value;
                        }
                    });
                    
                    // Hide bar
                    floatingSave.classList.remove('show');
                } else {
                    alert(result.error || 'Failed to save');
                }
            } catch (err) {
                console.error(err);
                alert('Network error');
            } finally {
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            }
        });
    }

    // Add Bad Word form handler
    const addWordForm = document.getElementById('addWordForm');
    if (addWordForm) {
        addWordForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const guildId = document.getElementById('bw_guild_id').value;
            const wordInput = document.getElementById('new_word');
            const word = wordInput.value.trim();
            
            if (!word) return;
            
            try {
                const response = await fetch('/api/add_bad_word', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ guild_id: guildId, word: word })
                });
                
                const result = await response.json();
                if (result.success) {
                    const list = document.getElementById('badWordsList');
                    const noWordsMsg = document.getElementById('no-words-msg');
                    if (noWordsMsg) noWordsMsg.remove();
                    
                    const newItem = document.createElement('div');
                    newItem.className = 'bad-word-tag';
                    newItem.setAttribute('data-word', word);
                    newItem.innerHTML = `
                        ${word}
                        <button type="button" onclick="removeWord('${word}')"><i class="fa-solid fa-xmark"></i></button>
                    `;
                    list.appendChild(newItem);
                    wordInput.value = '';
                } else {
                    alert(result.error || 'Failed to add word');
                }
            } catch (err) {
                console.error(err);
                alert('An error occurred while adding the word.');
            }
        });
    }
});

// Global function to remove bad word
async function removeWord(word) {
    if (!confirm(`Are you sure you want to remove "${word}"?`)) return;
    
    const guildId = document.getElementById('bw_guild_id').value;
    
    try {
        const response = await fetch('/api/remove_bad_word', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ guild_id: guildId, word: word })
        });
        
        const result = await response.json();
        if (result.success) {
            const item = document.querySelector(`.bad-word-tag[data-word="${word}"]`);
            if (item) {
                item.remove();
            }
        } else {
            alert(result.error || 'Failed to remove word');
        }
    } catch (err) {
        console.error(err);
        alert('An error occurred while removing the word.');
    }
}
