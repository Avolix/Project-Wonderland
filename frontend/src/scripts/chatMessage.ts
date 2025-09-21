export interface IChatMessage {
    actor: string, //the character or persona speaking
    text: string, //the text being spoken
    id: number,
    appendToText(append: string): void
}

export class ChatMessage implements IChatMessage{
    public id: number = Date.now() + Math.random();
    public actor: string = "";
    public text: string = "";
    constructor(actor: string, text: string) {
        this.actor = actor
        this.text = text
    };

    public appendToText(append: string): void {
        this.text += append;
    }
}