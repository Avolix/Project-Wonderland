<script lang="ts">
    import {ChatMessage} from "../scripts/chatMessage"
    import ChatMessageComponent from "./chatMessageComponent.svelte";
    import SvelteVirtualList from "@humanspeak/svelte-virtual-list";

    let currentText =$state("");

    let chatMessages = $state([
        new ChatMessage("Owner 1", "Test Message"),
        new ChatMessage("Owner 2", "Test Message.")
    ]);

    function addMessage() {
        chatMessages.push(new ChatMessage("User", currentText));
    };

</script>

<div style="height: 90vh;">
    <SvelteVirtualList items={chatMessages} debug>
        {#snippet renderItem(message)}
            <ChatMessageComponent chatMessage={message}/>
        {/snippet}
    </SvelteVirtualList>
</div>

<textarea bind:value={currentText}>
    
</textarea>

<button onclick={addMessage}>
	Click Me
</button>