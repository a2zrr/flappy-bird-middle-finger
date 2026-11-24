import java.awt.BorderLayout;
import javax.swing.*;

public class App {
    public static void main(String[] args) throws Exception {
        JFrame frame = new JFrame("Flappy Bird");
        frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        frame.setResizable(false);
        frame.setLayout(new BorderLayout());

        // The game board on the left, the webcam image from the tracker beside it.
        FlappyBird flappyBird = new FlappyBird();
        CameraFeedListener.CameraPanel camera = new CameraFeedListener.CameraPanel(320, 240);
        frame.add(flappyBird, BorderLayout.CENTER);
        frame.add(camera, BorderLayout.EAST);

        new UdpGestureListener(flappyBird, UdpGestureListener.DEFAULT_PORT).start();
        new CameraFeedListener(CameraFeedListener.DEFAULT_PORT, camera::setFrame).start();

        frame.pack();
        frame.setLocationRelativeTo(null); // centered on the screen
        frame.setVisible(true);
        // Keys only reach the board once the window is showing and has focus.
        flappyBird.requestFocusInWindow();
    }
}
