import tkinter as Tk
from grouping import SimpleSwitch13
class MainFrame(Tk.Frame):

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.initUI()


    def initUI(self):

        self.master.title("Simple menu")

        menubar = Tk.Menu(self.master)
        self.master.config(menu=menubar)

        self.frame = Tk.Frame(self.parent)
        self.frame.pack()

        fileMenu = Tk.Menu(menubar)
        fileMenu.add_command(label="Exit", command=self.onExit)

        menubar.add_cascade(label="File", menu=fileMenu)

        self.v = Tk.StringVar()
        self.v.set("1")
        self.om = Tk.OptionMenu(self.frame, self.v, "1", "2", "3")
        self.om.grid(row=0, column=0)
        # yesBut = Tk.Button(self.frame, text="Yes")
        # yesBut.grid(column=1, row=1)
        #
        # query = Tk.Label(self.frame, fg="#00ff00", bg="#001a00", anchor="w")
        # query.grid(column=1, row=0, columnspan=2, sticky="ew")

    def onExit(self):

        self.quit()


def main():

    root = Tk.Tk()
    root.geometry("1366x768")
    app = MainFrame(root)
    root.mainloop()


if __name__ == '__main__':
    main()
