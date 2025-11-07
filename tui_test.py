from textual.app import App, ComposeResult
from textual.widgets import Footer, Label, ListItem, ListView, Button, Static
from textual.containers import Vertical


class ListViewExample(App):
    

    def compose(self) -> ComposeResult:
        self.test = Static("hmm")
        self.myList = ListView(
            ListItem(Label("hello")),
        )

        yield Vertical (
            self.test,
            self.myList
        )
        yield Button ("test", id="test")
        yield Button ("clear", id="clear")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "test":
            self.myList.append(Static("world - static"))
            self.myList.append(Label("world - label"))
            self.test.update("button works")

        if event.button.id == "clear":
            self.test.update("clear")
            self.myList.remove_children()

if __name__ == "__main__":
    app = ListViewExample()
    app.run()