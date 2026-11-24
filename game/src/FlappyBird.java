import java.awt.*;
import java.awt.event.*;
import java.util.ArrayList;
import javax.swing.*;

public class FlappyBird extends JPanel implements ActionListener, KeyListener {
    int boardWidth = 360;
    int boardHeight = 640;

    
    Image backgroundImg;
    Image birdImg;
    Image topPipeImg;
    Image bottomPipeImg;


    class Bird {
        int x = boardWidth/8;
        int y = boardHeight/2;
        int width = 34;
        int height = 24;
        Image img;

        Bird(Image img) {
            this.img = img;
        }
    }

    //pipe class
    int pipeX = boardWidth;
    int pipeY = 0;
    int pipeWidth = 64;  // 1/6
    int pipeHeight = 512;
    
    class Pipe {
        int x = pipeX;
        int y = pipeY;
        int width = pipeWidth;
        int height = pipeHeight;
        Image img;
        boolean passed = false;

        Pipe(Image img) {
            this.img = img;
        }
    }

    //game logic
    Bird bird;
    int velocityX = -4; 
    int velocityY = 0; 
    int gravity = 1;

    ArrayList<Pipe> pipes;
    

    Timer gameLoop;
    Timer placePipeTimer;
    boolean gameOver = false;
    double score = 0;
    JFrame gameOverFrame; // kept so a restart can close the game-over window
    long gameOverAt = 0; // when the game ended (ms), used by the FLAP lockout
    static final int GAME_OVER_FLAP_LOCKOUT_MS = 800;

    // Corner HUD fed by the tracker's STATUS messages. HUD_HIDDEN until one arrives.
    static final int HUD_HIDDEN = -1, HUD_NO_HAND = 0, HUD_HAND = 1, HUD_FINGER_UP = 2;
    int handStatus = HUD_HIDDEN;

    // The bird waits until the first flap (SPACE or middle finger) starts the game.
    boolean started = false;

    FlappyBird() {
        setPreferredSize(new Dimension(boardWidth, boardHeight));

        setFocusable(true); 
        addKeyListener(this);

        backgroundImg = new ImageIcon(getClass().getResource("./flappybirdbg.png")).getImage();
        birdImg = new ImageIcon(getClass().getResource("./flappybird.png")).getImage();
        topPipeImg = new ImageIcon(getClass().getResource("./toppipe.png")).getImage();
        bottomPipeImg = new ImageIcon(getClass().getResource("./bottompipe.png")).getImage();

    
        bird = new Bird(birdImg);

        pipes = new ArrayList<Pipe>();


        placePipeTimer = new Timer(1500, new ActionListener() {
            @Override
            public void actionPerformed(ActionEvent e) {
            
              placePipes();
            }
        });
        

		gameLoop = new Timer(1000/60, this); 
        gameLoop.start();
	}
    
    void placePipes() {
        //  -pipeHeight/4 ->   -3/4 pipeHeight
        int randomPipeY = (int) (pipeY - pipeHeight/4 - Math.random()*(pipeHeight/2));
        int openingSpace = boardHeight/4;
    
        Pipe topPipe = new Pipe(topPipeImg);
        topPipe.y = randomPipeY;
        pipes.add(topPipe);
    
        Pipe bottomPipe = new Pipe(bottomPipeImg);
        bottomPipe.y = topPipe.y  + pipeHeight + openingSpace;
        pipes.add(bottomPipe);
    }
    
    
    public void paintComponent(Graphics g) {
	super.paintComponent(g); 
		draw(g);
	}

	public void draw(Graphics g) {
        
        g.drawImage(backgroundImg, 0, 0, this.boardWidth, this.boardHeight, null);

        g.drawImage(birdImg, bird.x, bird.y, bird.width, bird.height, null);
  

     //pipes
        for (int i = 0; i < pipes.size(); i++) {
            Pipe pipe = pipes.get(i);
            g.drawImage(pipe.img, pipe.x, pipe.y, pipe.width, pipe.height, null);
        }

        //score
        g.setColor(Color.white);

        g.setFont(new Font("Arial", Font.PLAIN, 32));
        if (!gameOver) {
            g.drawString(String.valueOf((int) score), 10, 35);
        }

        drawHud(g);
        
        
	}

    public void move() {
        //bird
        velocityY += gravity;
        bird.y += velocityY;
        bird.y = Math.max(bird.y, 0);

        //pipes
        for (int i = 0; i < pipes.size(); i++) {
            Pipe pipe = pipes.get(i);
            pipe.x += velocityX;

            if (!pipe.passed && bird.x > pipe.x + pipe.width) {
                score += 0.5; // 0.5*2 = 1
                pipe.passed = true;
            }

            if (collision(bird, pipe)) {
                gameOver = true;
            }
        }

        if (bird.y > boardHeight) {
            gameOver = true;
        }
    }

    boolean collision(Bird a, Pipe b) {
        return a.x < b.x + b.width &&   //a's top left corner doesn't reach b's top right corner
               a.x + a.width > b.x &&   //a's top right corner passes b's top left corner
               a.y < b.y + b.height &&  //a's top left corner doesn't reach b's bottom left corner
               a.y + a.height > b.y;    //a's bottom left corner passes b's top left corner
    }

    
    @Override
    public void actionPerformed(ActionEvent e) { 
       
        if (!started) {
            repaint();
            return;
        }
        move();
        repaint();
        if (gameOver) {
            gameOverAt = System.currentTimeMillis();
            placePipeTimer.stop();
            gameLoop.stop();
            showGameOverFrame();
        }
    }  

    @Override
    public void keyPressed(KeyEvent e) {
        if (e.getKeyCode() == KeyEvent.VK_SPACE) {

            jump();
           

        }
    }

    @Override
    public void keyTyped(KeyEvent e) {}

    @Override
    public void keyReleased(KeyEvent e) {}

    // One flap: the same action SPACE performs.
    void jump() {
        if (!started) {
            started = true;
            placePipeTimer.start();
        }
        velocityY = -9;
    }

    // Reset everything and start playing again (used by the Restart button).
    void restartGame() {
        bird.x = boardWidth / 8;
        bird.y = boardHeight / 2;
        velocityY = 0;
        pipes.clear();
        score = 0;
        gameOver = false;

        started = false; // back to the start screen; the next flap plays
        gameLoop.start();
        if (gameOverFrame != null) {
            gameOverFrame.dispose();
            gameOverFrame = null;
        }
        repaint();
        requestFocusInWindow();
    }

    // Called on the Swing thread with the tracker's STATUS message.
    void setHandStatus(boolean handPresent, boolean gestureOn) {
        if (!handPresent) {
            handStatus = HUD_NO_HAND;
        } else {
            handStatus = gestureOn ? HUD_FINGER_UP : HUD_HAND;
        }
        repaint();
    }

    // Small pill in the top-right corner showing what the webcam sees.
    void drawHud(Graphics g) {
        String text;
        Color dot;
        switch (handStatus) {
            case HUD_NO_HAND:
                text = "no hand";
                dot = new Color(150, 150, 150);
                break;
            case HUD_HAND:
                text = "hand detected";
                dot = new Color(255, 200, 0);
                break;
            case HUD_FINGER_UP:
                text = "finger UP";
                dot = new Color(80, 220, 90);
                break;
            default:
                return; // no tracker connected: nothing to show
        }
        g.setFont(new Font("Arial", Font.BOLD, 13));
        int width = g.getFontMetrics().stringWidth(text) + 30;
        int x = boardWidth - width - 10;
        int y = 10;
        g.setColor(new Color(0, 0, 0, 150));
        g.fillRoundRect(x, y, width, 24, 12, 12);
        g.setColor(dot);
        g.fillOval(x + 9, y + 8, 8, 8);
        g.setColor(Color.white);
        g.drawString(text, x + 22, y + 17);
    }

    // A FLAP from the webcam: jump, or restart if the game is over.
    void handleFlap() {
        if (gameOver) {
            // Ignore the flap that may have ended the game so it can't restart it instantly.
            if (System.currentTimeMillis() - gameOverAt < GAME_OVER_FLAP_LOCKOUT_MS) {
                return;
            }
            restartGame();
        } else {
            jump();
        }
    }

    private void showGameOverFrame() {
        gameOverFrame = new JFrame("Game Over");
        gameOverFrame.setSize(300, 200);
        gameOverFrame.setLayout(new BorderLayout());
        gameOverFrame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
    
        JLabel gameOverLabel = new JLabel("Game Over! Score: " + (int) score, SwingConstants.CENTER);
        gameOverLabel.setFont(new Font("Arial", Font.BOLD, 20));
        gameOverLabel.setForeground(Color.RED);
    
        JButton restartButton = new JButton("Restart");
        restartButton.addActionListener(e -> restartGame());
    
        gameOverFrame.add(gameOverLabel, BorderLayout.CENTER);
        gameOverFrame.add(restartButton, BorderLayout.SOUTH);
    
        gameOverFrame.setLocationRelativeTo(null);
        gameOverFrame.setVisible(true);
    }
}