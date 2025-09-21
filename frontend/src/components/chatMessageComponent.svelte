<script lang='ts'>
    import { fade } from 'svelte/transition';
    import type { IChatMessage } from '../scripts/chatMessage.js';

    let { chatMessage }: {chatMessage: IChatMessage} = $props()
</script>

<div class="chatMessage">
    <h3 transition:fade>{chatMessage.actor}</h3>
    <p transition:fade>
        {@html chatMessage.text}
    </p>
</div>